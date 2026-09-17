/**
 * THE GUIDE — presence
 *
 * Counts the sets that are on, and which channel each is tuned to.
 *
 * One Durable Object holds the whole dial, so the count is exact rather than
 * sampled: a viewer *is* a live WebSocket, and tuning out is that socket
 * closing. There is no database here, no cookie and no identifier — nothing
 * survives the connection, so there is nothing to keep, leak or delete.
 *
 * This matters more here than on a normal site. The schedule is a pure
 * function of wall-clock time, so everyone on CH 12 is on the same frame of
 * the same film. A per-channel count is not traffic, it is a rating.
 */

const ALLOW = [
  'https://bonjorno2.github.io',
  'http://localhost:8744',          // python -m http.server, per .claude/launch.json
  'http://127.0.0.1:8744',
];

const MAX = 5000;                   // a runaway-billing stop, not a capacity limit
const KEY = /^[mp][0-9]{1,3}$/;     // guide + channel number: m12 is CH 12, p1 is a pick

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const origin = req.headers.get('Origin');

    // The operator's view. Public on purpose: it is one integer and a
    // histogram, nothing here is worth hiding behind a key.
    if (url.pathname === '/count') return dial(env).fetch('https://dial/count');

    if (url.pathname !== '/tune') return new Response('not found', { status: 404 });

    // A browser always sends Origin on a WebSocket handshake, so a missing one
    // is a script rather than a viewer. Neither gets to inflate the rating.
    if (!ALLOW.includes(origin)) return new Response('forbidden', { status: 403 });
    if (req.headers.get('Upgrade') !== 'websocket')
      return new Response('expected a websocket', { status: 426 });

    return dial(env).fetch(req);
  },
};

// One object for the whole world. The dial is small and a counter is not
// latency-sensitive, so there is no reason to shard it.
const dial = env => env.DIAL.get(env.DIAL.idFromName('dial'));

export class Dial {
  constructor(state) {
    this.state = state;
    // Answer the client keepalive at the edge. Without this, every ping from
    // every viewer would wake the object and an idle dial would bill for its
    // own silence.
    state.setWebSocketAutoResponse(new WebSocketRequestResponsePair('p', 'o'));
  }

  async fetch(req) {
    if (new URL(req.url).pathname === '/count')
      return Response.json(this.tally(), {
        headers: { 'access-control-allow-origin': '*', 'cache-control': 'no-store' },
      });

    if (this.state.getWebSockets().length >= MAX)
      return new Response('dial full', { status: 503 });

    const [client, server] = Object.values(new WebSocketPair());
    // Hibernation: the object may be evicted while these sockets stay open,
    // and is woken by a message or a close. Everything it needs to recover
    // therefore lives on the socket, not on `this`.
    this.state.acceptWebSocket(server);
    server.serializeAttachment(null);        // no channel until they tell us one

    // Answer the newcomer directly rather than letting broadcast() do it: a
    // join that lands in the same instant as a departure leaves the tally
    // unchanged, and a deduplicated broadcast would never reach them.
    try { server.send(JSON.stringify(this.tally())) } catch (e) {}
    this.broadcast();

    return new Response(null, { status: 101, webSocket: client });
  }

  webSocketMessage(ws, msg) {
    if (typeof msg !== 'string' || !KEY.test(msg)) return;   // junk keys stay out of the map
    if (ws.deserializeAttachment() === msg) return;
    ws.serializeAttachment(msg);
    this.broadcast();
  }

  // The departing socket is still in getWebSockets() while its handler runs,
  // so it has to be named and skipped. Counting it would produce a tally
  // identical to the last one, broadcast() would suppress it as a duplicate,
  // and every viewer would keep showing the leaver until somebody else moved.
  webSocketClose(ws) { this.broadcast(ws) }
  webSocketError(ws) { this.broadcast(ws) }

  tally(skip) {
    const socks = this.state.getWebSockets().filter(ws => ws !== skip);
    const ch = {};
    for (const ws of socks) {
      let k = null;
      try { k = ws.deserializeAttachment() } catch (e) {}
      if (k) ch[k] = (ch[k] || 0) + 1;
    }
    return { n: socks.length, ch };
  }

  /* Broadcasts are driven by people joining, leaving and tuning, so the rate
     is bounded by what viewers actually do. If this ever carries thousands at
     once, coalesce on a short timer — note that a hibernating object can lose
     a pending one, so it would need to survive eviction. */
  broadcast(skip) {
    const msg = JSON.stringify(this.tally(skip));
    if (msg === this.last) return;           // `last` is lost on hibernation; a
    this.last = msg;                         // duplicate broadcast is harmless
    for (const ws of this.state.getWebSockets()) {
      if (ws === skip) continue;
      try { ws.send(msg) } catch (e) {}
    }
  }
}

"""Cases for drivein.bill() and drivein.retitle().

The bill is read out of eleven years of one person's freeform prose, so every
case here is a real description from the shelf, trimmed to the sentences that
matter. The rejections are the point: each one is a real film, on archive.org,
named in the blurb, that is *not* what plays tonight.

    python test_drivein.py
"""
import sys

from drivein import bill, retitle, norm

# Every title any case needs to be recognised as a real film. Stands in for
# ia-curation's catalog scrape, which is 110,794 of these.
KNOWN = {norm(t) for t in [
    "The Little Shop of Horrors", "A Bucket of Blood", "Assignment Terror",
    "Count Dracula's Great Love", "Cosmos: War of the Planets",
    "War of the Robots", "Star Wars", "Starcrash", "Drive In Massacre",
    "Panic", "Popeye", "The City of The Dead", "Horror Hotel",
    "The Naked Witch", "Missile To The Moon", "Cat-Women Of The Moon",
    "The Lost Missile", "The Cosmic Man", "Spooks Run Wild",
    "Ghosts On The Loose", "One Body Too Many", "Tin Man",
    "Night of the Living Dead", "Carnival of Souls", "Deadland",
    "Invasion USA", "Unknown World", "Duck And Cover", "Target You",
    "The Giant Gila Monster", "The Killer Shrews",
    "Attack of The Giant Leeches", "Dementia 13", "Demented",
    "Burn Witch Burn", "Night of the Eagle", "The Devil's Hand",
    "Yongary, Monster From The Deep", "Monster From A Prehistoric Planet",
    "Gappa", "Tarzan - The Fearless", "The New Adventures of Tarzan",
    "Tarzan And The Green Goddess", "The Snow Creature", "Manfish",
]}

CASES = [
    # (week title, description, expected bill, what it is testing)
    (
        'Shocker Internet Drive In - Week 14: "Corman Creature Feature"',
        'Tonight we proudly present a Roger Corman double feature. Grab your '
        'munchies from the snack bar and enjoy a bite with Aldry in "The Little '
        'Shop of Horrors" and then finish out the night with a little bit of art '
        'in "A Bucket of Blood". Of course we tempt you with the usual trailers, '
        'advertisements and a wonderfully racy Tex Avery cartoon.',
        ["The Little Shop of Horrors", "A Bucket of Blood"],
        "the plain case: two features, extras in their own sentence",
    ),
    (
        'Shocker Internet Drive In - Week 18: "A Naschy Double Feature"',
        'After some choice previews of some of Paul\'s more famous flicks, we '
        'present the wide screen version of that 1970 monster fest "Assignment '
        'Terror" (also featuring Michael Rennie), followed by the 1973 boob and '
        'blood feast - "Count Dracula\'s Great Love" (Parental Guidance suggested).',
        ["Assignment Terror", "Count Dracula's Great Love"],
        "both features in one sentence, one behind 'followed by'",
    ),
    (
        'Shocker Internet Drive In - Week 46: "Sci-Fi Spaghetti" Double Feature',
        'With Spring about to spring, we thought we would things up with some '
        'Italian science fiction guaranteed to make you yearn for the good old '
        'days of "Star Wars" (or even "Starcrash"). After some wonderful coming '
        'attractions and a Road Runner cartoon, we gladly bring you "Cosmos: War '
        'of the Planets", an epic of confusion. Then, after a brief intermission, '
        'we happily present "War of the Robots", another epic of confusion!',
        ["Cosmos: War of the Planets", "War of the Robots"],
        "a comparison is not a booking: Star Wars is not playing",
    ),
    (
        'Shocker Internet Drive In - Week 12: Massacre Double Feature',
        'And - by popular demand - we are proud to bring you the that 1976 '
        'classic of low budget fun "Drive In Massacre"! In addition to a classic '
        '"Popeye" cartoon and the usual Snack Bar plugs, we are also presenting '
        '"Panic" another low budget wonder from the 1970\'s.',
        ["Drive In Massacre", "Panic"],
        "the cartoon is named and quoted and is still the cartoon",
    ),
    (
        'Shocker Internet Drive In - Week 56: "Which Witch" Double Feature',
        'First up, after the usual Coming Attractions, we bring you a Bugs '
        'cartoon, with "witch" comes a few laughs, followed by Christopher Lee '
        'and "The City of The Dead" (or "Horror Hotel" - which ever scares you '
        'the most). Then, after a brief intermission and a voodoo short, we '
        'conclude the night with Larry Buchanan\'s "The Naked Witch".',
        ["The City of The Dead", "The Naked Witch"],
        "one picture with two names is one picture",
    ),
    (
        'Shocker Internet Drive In Week 113: "Summer Sci-Fi" Triple Feature',
        'First up, after a few coming attractions, we begin the fun with '
        '"Missile To The Moon", a 1958 low budget remake of "Cat-Women Of The '
        'Moon". Then, we continue with 1958\'s "The Lost Missile" about some '
        '"alien" rocket destroying things here on earth. Finally, we close out '
        'the triple treat with 1959\'s "The Cosmic Man".',
        ["Missile To The Moon", "The Lost Missile", "The Cosmic Man"],
        "the film it is a remake of is not on the bill",
    ),
    (
        'Shocker Internet Drive In - Week 55: "Bela Claus" Triple Feature',
        'Yes Kiddies, everyone\'s favorite haunted drive-in is happy to present '
        'our Xmas Spectacular with three of the King\'s goofier films - two also '
        'starring the East Side Kids as well as one featuring Mr. Jack Haley '
        '(the "Tin Man"). First up, after some Christmas messages and a Max '
        'Fleischer holiday cartoon, we get right to it with "Spooks Run Wild" '
        'followed by another East Side Kids\' feature "Ghosts On The Loose". '
        'Then, after a few more good wishes, we close out our night with "One '
        'Body Too Many".',
        ["Spooks Run Wild", "Ghosts On The Loose", "One Body Too Many"],
        "an actor's nickname that happens to also be a film",
    ),
    (
        'Shocker Internet Drive In Week 4 - Night of the Living Dead Double Feature',
        'Tonight we present are presenting a black & white double feature in '
        '"Deadland". After an early Porky Pig cartoon, we proudly present the '
        'George A. Romero classic "Night of the Living Dead", sourced from a nice '
        'print by the way. And if that wasn\'t enough, we close out our show with '
        'another "dead" cult classic - "Carnival of Souls"!',
        ["Night of the Living Dead", "Carnival of Souls"],
        "'double feature in X' names the night, not a film in it -- and the "
        "week is titled after the picture it opens with, so no theme rule "
        "can reject one without rejecting the other",
    ),
    (
        'Shocker Internet Drive In - Week 53: "Halloween Nuclear Horrors" Double Feature',
        'First up, after the usual coming attractions, we bring you that classic '
        'school house short subject, "Duck And Cover". Then we bring you '
        '"Invasion USA" an action filled cautionary tale. Finally, following a '
        'brief intermission featuring another atomic short, "Target You", we '
        'conclude our nuclear horrors with "Unknown World".',
        ["Invasion USA", "Unknown World"],
        "two shorts, both announced by the same verb as the features",
    ),
    (
        'Shocker Internet Drive In Week 8 - Terror Triple Feature',
        'Tonight we bring you "The Giant Gila Monster", "The Killer Shrews" and '
        '"Attack of The Giant Leeches".',
        ["The Giant Gila Monster", "The Killer Shrews",
         "Attack of The Giant Leeches"],
        "three in a row, one verb",
    ),
    (
        'Shocker Internet Drive In Week 1',
        'Welcome to the first night of the Shocker Internet Drive In. Sit back '
        'and enjoy the show.',
        [],
        "nothing named: bill nothing rather than guess",
    ),
    (
        'Shocker Internet Drive In - Week 126: "The Devil You Say" Double Feature',
        'First up, after the normal coming attractions and cartoon, we present '
        '1961\'s "The Devil\'s Hand" about a group of "Gamba" Devil worshipers. '
        'Then, after a brief intermission, we finish up with "Burn Witch Burn" '
        '(aka "Night of the Eagle"), a 1962 offering about a wife.',
        ["The Devil's Hand", "Burn Witch Burn"],
        "an aka in brackets is the same film again",
    ),
    (
        'Shocker Internet Drive In ~ Week 36: "Mother\'s Day Massive Monsters" '
        'Double Feature',
        'After a few "giant" coming attractions and a Bugs Bunny cartoon, we '
        'bring you Korea\'s answer to Godzilla "Yongary, Monster From The Deep". '
        'Then, following a brief intermission featuring a "feminine" touch, our '
        'second movie is "Monster From A Prehistoric Planet" (also known as '
        '"Gappa").',
        ["Yongary, Monster From The Deep", "Monster From A Prehistoric Planet"],
        "'our second movie is' announces a feature too",
    ),
    (
        'Shocker Internet Drive In Week 123: "Tarzan Triple"',
        'First up, after some MGM previews, we begin with Buster Crabbe as '
        '"Tarzan - The Fearless", a condensed feature of a "lost" serial. Next '
        'up, we finish things up with "The New Adventures of Tarzan" as well as '
        '"Tarzan And The Green Goddess".',
        ["Tarzan - The Fearless", "The New Adventures of Tarzan",
         "Tarzan And The Green Goddess"],
        "two features share one clause",
    ),
    (
        'Shocker Internet Drive In - Week 49: "A Wild - Wilder" Double Feature',
        'First up, after some "serial" fun and a jiving cartoon, Billy\'s older '
        'brother brings us 1954\'s "The Snow Creature" about an abominable '
        'snowman. Following another wonderful intermission, we encourage '
        'everyone to take a swim with "Manfish", Wilder\'s take on Poe.',
        ["The Snow Creature", "Manfish"],
        "the announcer is not always 'we'",
    ),
    (
        'Shocker Internet Drive In - Week 13: "Demented" Double Feature',
        'Well after some major renovations we are pleased to announce that your '
        'friendly neighborhod Shocker Drive In is back open! Tonight we present '
        '"Dementia 13" and "The House On Haunted Hill".',
        [],
        "a declared double that reads as something else bills nothing "
        "(House On Haunted Hill is absent from this catalog)",
    ),
]

RETITLE = [
    ('Shocker Internet Drive In - Week 18: "A Naschy Double Feature"',
     "Week 18: A Naschy Double Feature"),
    ("Shocker Internet Drive In Week 3 - Frankenstein Double Feature",
     "Week 3 - Frankenstein Double Feature"),
    ('Shocker Internet Drive In ~ Week 36: "Mother\'s Day Massive Monsters" '
     'Double Feature',
     "Week 36: Mother's Day Massive Monsters Double Feature"),
    ("REVISED-Shocker Internet Drive In Week 7 REDO - Vampires",
     "Week 7 REDO - Vampires"),
    ('Shocker Internet Drive In - Week 50: "Moon Men" Marathon',
     "Week 50: Moon Men Marathon"),
]


def main():
    bad = 0
    for title, desc, want, why in CASES:
        got = bill(desc, title, KNOWN)
        if got != want:
            bad += 1
            print(f"FAIL  {why}\n      {title}\n      want {want}\n      got  {got}")
    for raw, want in RETITLE:
        got = retitle(raw)
        if got != want:
            bad += 1
            print(f"FAIL  retitle\n      want {want!r}\n      got  {got!r}")
    total = len(CASES) + len(RETITLE)
    print(f"{total - bad}/{total} pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

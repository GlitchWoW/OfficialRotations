PvP Disco Priest

Build:
Arena
- CAQAJSbRac/22NxZbHdYKOQzcADw2sMDDzyMAMbzsMzMzMmZAAAAAAAAAAAY2sMbMmZGwYWMGmhZzYmmZCGYmZmNsQxYWmZZ22M2MWsB

BGs
- CAQAJSbRac/22NxZbHdYKOQzcADw2sMDDzyMDgZbmlZmZMmZAAAAAAAAAAAwmtZjxMzMwYWMzghZzsYamJYAMzG2oYMLDwYBLA

PvP talents: 
- Arena: Phase Shift, Inner Light & Shadow, Ultimate Radiance
- BGs: Phase Shift, Ultimate Radiance, Archangel

Stat prio: 
- Vers > Mastery > Haste > Crit

Trinkets:
- use Badge for the HP defensive or Alacrity for main stat proc

Notes:

Changelog:
28/02/2025 - v0.1.7
- Adjusted UP usage

18/02/2025 - v0.1.6
- Added some randomization to dispelling

14/10/2024 - 0.1.5-1
- Tweaked the renew stuff for BGs

04/10/2024 - v0.1.5
- Small fixes
- PI now respects the toggle

01/09/2024 - v0.1.4 + v0.1.4-1
0.1.4-1
- Addresses some of the issues where it feels like it does nothing

0.1.4
- Lots of undocumented changes from 0.1.3-1 through 0.1.3-6 (gotta love it right)
- A try to tweak barrier, it seems like sometimes it just pops it for no seemingly good reason
- Tweaking on the holdGCD logic

30/09/2024 - v0.1.3-1
- Moved channel check to states

29/09/2024 - v0.1.3
- Dont hold GCD when in BGs
- Fix on some pvp functions, mainly the CC check
- Fix for inner light & shadow, it was constantly switching
- Purify/Dispel fixes for offensive and defensive modes

- 27/09/2024 - v0.1.2 + 0.1.2-1 + 0.1.2-2 + 0.1.2-3 + 0.1.2-4

0.1.2-4
- Added Schism to the rotation since we use it in BG talents

-2 + -3
- Bug fixes

0.1.2-1
- Added a "WoE ultralow" to force WoE spending even if casting/channeling if our friend falls too low (currently below 20%, tune in settings, and no shields up)

0.1.2
- Added scream for interrupts if enemies within range and casting from our interrupt list
- Several adjustments to the code to improve performance

- 26/09/2024 - v0.1.1 + 0.1.1-1 + 0.1.1-2
0.1.1-2
- Attempt to fix double radiance
- Moved some things to states to (hopefully) force them being updated properly

- 0.1.1-1
- WoE specific logic to force shields out with the buff
- Fixed dumb error

- 0.1.1
- Some fixed errors
- Adjustments to how we use penance, we will use it much more offensively for WoE
-- penanceHP setting reduced to 20 from 60

26/09/2024 - v0.1.0
- Initial release
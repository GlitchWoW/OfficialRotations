Note:
You need to bind "Pet Attack" in your WoW settings

Talents:
- Guillotine M+: 
BoQAj5LiEN4VXhSin5RcWeAUgoBSSkkQkmCRaSSIlAAAAAgWEISiWEhkkEplkkQAAAAAAQSA
- Raid Cleave: 
BoQAAAAAAAAAAAAAAAAAAAAAAAIJRSCkmCRaJJh0CAAAAAQwBikkSERSikSaJRCBAAAAAAJC
- Raid ST: 
BoQAAAAAAAAAAAAAAAAAAAAAAAIJRSCkmCRaJJh0CAAAAAIBSikSEhkIpolkkQAAAAAAQiA

Special thanks:
Big thanks to Boomcats & Thombo

Changelog:
24/07/2024
- Fix for the new vilefiend
- Use vilefiend more often!

15/06/2024
- Added some specific trinket logic for on CD

13/06/2024
- Added Mouseover bres toggle
- Corrected some dreambinder logic

5/3/2024
- Added Dreambinder and Nymue usage

4/29/2024
- Fixed some double defensive usage

4/26/2024
- Added Soulburn for healthstones

4/25/2024
- Added a few extra logic steps to auto ramp
- Added TTD slider

4/10/2024
- Added delay settings for AOE placements (Shadowfury, Guillotine)

3/4/2024
- Done some changes to toggles:
-- Auto ramp - This will use 'Auto ramp mode'
-- quick ramp = This will enable small ramp/quick ramp scenarios manually
-- full ramp = this will enable the full ramp manually.
Quick ramp/Full ramp toggles should NOT be used if using auto ramp.

3/30/2024
- Added fallbacks for AOE placements

3/29/2024
- Changed up a few methods to common modules.
- Switched away from optimized aoe to onTarget.

18/03/2024
- Changed up a few methods to common things
- Changed up some smaller logic to (hopefully) fix the spreading issues

20/02/2024
- Auto trinket ID
- Iridal usage
- Trinket distance for Belor'elos
- Potions

16/2/2024
- dont CD on spiteful mobs

1/29/2024
- Changed Guillotine logic to use the 'castOptimized'
- Changed small ramp condition to not fire off if GFG has 30 seconds or less cd

1/8/2024
- Settings variable to control imp count on implosion
- Fixed doom brand spreading
- Properly fixed the 'small ramp' condition

1/7/2024
- Added proactive defensives

6/1/2023
- Added tyrant Up check for demonic strenght
- Adjusted tyrant timers to be a bit smaller to get it out quicker
- Spend insta demonbolts while moving

2/4/2023
- Changed big ramp logic
- Added interrupts with Axe toss (and toggle + setting for it)

1/4/2023
- Moved power siphon to main builder logic (to use it more often)
- Shadowfury should now only be used on aoe
- Implosion should now only be used on aoe
- Fixed trinket 'Self' condition
- Fixed tyrant usage
- Added custom Implosion logic

1/2/2023
- Added 'Quick ramp'(or dirty ramp *wink* *wink*) mode (Toggle this in settings)
- Also for quick ramp, a complete rewrite on how we handle tyrant ramps
- Added trinket usage (Be sure to keybind the trinket on a spellbar slot!! Get the ID on your trinket with the addon 'idTip')

12/27/2023
- Now using the new optimized AOE

12/24/2023
- Fixed fear on affix units (hopefully)
- Group TTD on implosion
- Group TTD on tyrant
- Added Fel Domination usage on summoning Felguard if its not present
- Added defensives usage (dark pact/unending resolve).

12/22/2023
- Initial BETA release
EDIT:
- Added Shadowfury usage on AOE auto (and fixed it..)
- Added pet attack (and fixed it..)
- Added auto fear on Affix (Incorporeal) units
- Added toggle to hold CDs
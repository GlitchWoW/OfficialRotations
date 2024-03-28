Talents:
- M+ (General purpose): 
BIQA0Hr2WRGgVq7/s2iQ2HhjlkAJCAAAAAAAAAAAAgEplEJJlISSkEJFQhkkEpJBiIRKSLkEUgA

Changelog:
27/5/2024
- fortitude to use common API
- Corrected PI call

3/5/2024
- Added backup target for shadow crash in case theres no tanks
- Added TTD check for shadow crash (>= 15)
- Added TTD check for Halo (>= 10)
- Added some movement checking for shadow crash

3/3/2024
- Added preliminary common racials module for testing

2/28/2024
- 3 new settings:
autoCrash = "Toggle this to enable automatic shadow crash usage"
forceCrash = "If you have auto crash disabled; You can use this to cast it on tank or if you just want to force crash usage"
unitsAroundTankSlider = "% of units in pull around tank for crash"
- Changes to how Shadow crash behaves now also with toggles to control it. 

2/21/2024
- Added a check to not cast vampiric touch if last cast was shadow crash
- Added a force single target toggle
- Reduced shadow crash vampiric count check a little bit
- Humanizer settings correctly applied to defensives

2/20/2024
- Added some proactive defensive stuff
- added silence interrupt following the interrupt prio list
- added MD for bursting
- changed a bit of the crash logic to also include the debuff count setting
- added force fear as a toggle

2/19/2024
- 'Cooldowns' and 'cooldownsTTD' settings tied to PI, mindbender, void eruption
- 'Maintain Debuff Count' setting to adjust how many units we are trying to maintain our debuffs on
- Shadow crash above all else for AOE to prio getting it out
- little adjustment for mind blast in regards to eruption and spending stacks
- Devouring plague much higher prio
- Added isFacing for divine star
- Fixed dot usage

2/18/2024
- Fixed auto retarget
- Some optimization changes
- Fix for voidform stuff (and fixed the ID ^^)
- Death's torment shadow crash (for aoe) and otherwise SWP on 9 stacks

2/9/2024
- Added auto retarget
- Removed deaths torment req for shadowcrash
- Cleaned up toggles a bit

1/2/2023
- Added trinket usage (Be sure to keybind the trinket on a spellbar slot!! Get the ID on your trinket with the addon 'idTip')

12/27/2023
- Now using the new optimized AOE
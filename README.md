# gtav-native-crossmap-generator

an abandoned project that aims to generate GTA V native hash translation tables by parsing and diffing the game scripts of 2 different game updates, by using multiple methods (call count matching, offset delta pattern matching, etc.)

1. extract the game scripts (*.ysc.full) from update.rpf\x64\levels\gta5\script\script_rel.rpf
2. put them in .\game_scripts\\`_version_`\
3. change the global variables in xmapgen.py accordingly

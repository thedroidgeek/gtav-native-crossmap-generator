# gtav-native-crossmap-generator

an abandoned project that aims to generate GTA V native hash translation tables by parsing and diffing the game scripts of 2 different game updates, by using multiple methods (call count matching, offset delta pattern matching, etc.)

1. *export* the game scripts (\*.ysc.full) from `update.rpf\x64\levels\gta5\script\script_rel.rpf` to `.\game_scripts\<version>\` using your mainstream modding tool
2. repeat for old update.rpf
3. put the old crossmap on a text file
4. change the global variables in xmapgen.py accordingly
  
**important**:
- no support shall be provided - do not pm me about this project whatsoever
- this project was publicized for educational purposes only, you are not allowed to use it to cheat and/or alter the gameplay of players without consent (or grant an ability to do so) on R* hosted sessions of GTA:O
- credit goes to Nathan James (zorg93/njames93) for the bytecode specification/opcodes extracted from his [decompiler](https://github.com/njames93/GTA-V-Script-Decompiler)

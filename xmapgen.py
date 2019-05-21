#!/usr/bin/env python

import os
import re
import struct
import datetime
import operator


old_script_foldername = 'game_scripts\\1493'
old_crossmap_filename = '1493_crossmap.txt'
new_script_foldername = 'game_scripts\\current'
new_crossmap_filename = 'crossmap_out.txt'
log_filename = 'logfile.txt'

min_pattern_size = 2 # a greater value means potentially less matches but more accuracy

old_script_data = {}
new_script_data = {}
generated_translations = {}
generated_translations_rev = {} # for fast reverse lookup


logf = open(log_filename, "w")

def log(message):
    timestamped = '%s %s' % (datetime.datetime.now().strftime("[%d-%m-%Y %H:%M:%S]"), message)
    print(timestamped)
    logf.write(timestamped + '\n')

def parse_native_calls(script_file_path):
    with open(script_file_path, "rb") as f:
        script_native_call_data = {}

        # parse header
        header_offset = 0
        if f.read(4) == b'RSC7':
            header_offset = 0x10
            f.read(header_offset)
        f.read(3 * 4)
        code_blocks_offset = struct.unpack('<I', f.read(4))[0] & 0xFFFFFF # 0x10
        f.read(2 * 4)
        code_len = struct.unpack('<I', f.read(4))[0] # 0x1C
        f.read(3 * 4)
        native_count = struct.unpack('<I', f.read(4))[0] # 0x2C
        f.read(4 * 4)
        native_offset = struct.unpack('<I', f.read(4))[0] & 0xFFFFFF # 0x40
        #log('native table at: %s, with %d natives' % (hex(native_offset), native_count))
        #log('code length: %d bytes' % code_len)

        f.seek(native_offset + header_offset)

        # decode native hashes
        script_native_call_data['table'] = []
        for i in range(native_count):
            value = struct.unpack('<Q', f.read(8))[0]
            rotate = (code_len + i) % 64
            script_native_call_data['table'].append(((value << rotate) | (value >> (64 - rotate))) & 0xFFFFFFFFFFFFFFFF)

        code_offset_table = []
        code_blocks = (code_len + 0x3FFF) >> 14

        f.seek(code_blocks_offset + header_offset)

        # get code block offsets
        for i in range(code_blocks):
            code_offset_table.append((struct.unpack('<I', f.read(4))[0] & 0xFFFFFF) + header_offset)
            f.read(4)

        # use them to read the code blocks
        bytecode = b''
        for i in range(code_blocks):
            f.seek(code_offset_table[i])
            bytecode += f.read((i + 1) * 0x4000 >= code_len and code_len % 0x4000 or 0x4000)

        # iterate through the instructions to find the native calls
        script_native_call_data['calls'] = []
        offset = 0
        last_offset = 0
        while offset < len(bytecode):
            if bytecode[offset] == 37:
                offset += 1
            elif bytecode[offset] == 38:
                offset += 2
            elif bytecode[offset] == 39:
                offset += 3
            elif bytecode[offset] == 40 or bytecode[offset] == 41:
                offset += 4
            elif bytecode[offset] == 44: # native
                native_index = (bytecode[offset + 2] << 8) | bytecode[offset + 3]
                script_native_call_data['calls'].append((native_index, (offset - last_offset) if last_offset > 0 else 0))
                last_offset = offset
                offset += 3
            elif bytecode[offset] == 45: # enter
                offset += bytecode[offset + 4] + 4
            elif bytecode[offset] == 46: # return
                offset += 2
            elif bytecode[offset] >= 52 and bytecode[offset] <= 66 and bytecode[offset] != 63:
                offset += 1
            elif bytecode[offset] >= 67 and bytecode[offset] <= 92:
                offset += 2
            elif bytecode[offset] >= 93 and bytecode[offset] <= 97:
                offset += 3
            elif bytecode[offset] == 98:
                offset += 1 + bytecode[offset + 1] * 6
            elif bytecode[offset] >= 101 and bytecode[offset] <= 104:
                offset += 1
            offset += 1

        return script_native_call_data


#
# stage 1: parse native table and native calls (instruction offset and native table index)
#          on script files that exist both on old and new release, then perform initial
#          translation using call count matching
#

files_list = []
for path, dirs, files in os.walk(old_script_foldername):
    for file in files:
        if file.endswith('.full'):
            files_list.append(file)

log('=> doing initial parsing and call count matching... this might take a little while...')

for i in range(len(files_list)):
    file = files_list[i]
    ori_code_len = 0
    code_len = 0
    new_script_path = new_script_foldername + '\\' + file[:-9] + '_ysc\\' + file
    old_script_path = old_script_foldername + '\\' + file[:-9] + '_ysc\\' + file
    if not os.path.isfile(new_script_path):
        continue
    old_script_data[file] = parse_native_calls(old_script_path)
    new_script_data[file] = parse_native_calls(new_script_path)
    old_calls = old_script_data[file]['calls']
    new_calls = new_script_data[file]['calls']
    old_table = old_script_data[file]['table']
    new_table = new_script_data[file]['table']
    if len(old_calls) == len(new_calls) and len(old_calls) > 0:
        added_translations = 0
        for j in range(len(old_calls)):
            old_native_hash = old_table[old_calls[j][0]]
            new_native_hash = new_table[new_calls[j][0]]
            if not new_native_hash in generated_translations:
                generated_translations[new_native_hash] = old_native_hash
                generated_translations_rev[old_native_hash] = new_native_hash
                added_translations += 1
            elif generated_translations[new_native_hash] != None and generated_translations[new_native_hash] != old_native_hash:
                log('[call count matching] WARNING: conflict found on 0x%016X, skipping for now...' % new_native_hash)
                del generated_translations_rev[generated_translations[new_native_hash]]
                generated_translations[new_native_hash] = None
        log('[call count matching] %s - %d (%d/%d) (+%d, total: %d)' % (file[:-9], len(old_calls), i+1, len(files_list), added_translations, len(generated_translations)))

# remove inconsistency 'markers'
i = 0
while i < len(generated_translations):
    key = list(generated_translations)[i]
    if generated_translations[key] != None:
        i += 1
    else:
        del generated_translations[key]

log('[call count matching] === translated %d natives! ===' % len(generated_translations))


#
# stage 2: use previously parsed call data to perform pattern detection based translation
#          which relies on call instruction offset delta and dynamic hash resolution
#

def generate_pattern(old_script, new_script, offset=0, low_accuracy_mode=False):
    largest_match = []
    old_calls = old_script['calls']
    old_table = old_script['table']
    new_calls = new_script['calls']
    new_table = new_script['table']
    # check offset validity
    if offset < 0 or offset >= len(old_calls):
        return []
    pattern_size = 0
    for i in range(len(new_calls)):
        pattern_size = 0
        for j in range(len(old_calls) - offset):
            # boundary check
            if i + j >= len(new_calls):
                break
            # compare offset
            if new_calls[i + j][1] != old_calls[j + offset][1]:
                break
            # compare hash, if possible
            if old_table[old_calls[j + offset][0]] in generated_translations_rev:
                if new_table[new_calls[i + j][0]] != generated_translations_rev[old_table[old_calls[j + offset][0]]]:
                    break
            # remember the largest match
            if len(largest_match) == 0 or j > largest_match[1] - largest_match[0] - 1:
                largest_match = [i, i + j + 1]
            pattern_size += 1
    # no need to continue if nothing was found
    if len(largest_match) == 0:
        return []
    # pattern quality check (single match on old) - inconsistencies occur without this
    if not low_accuracy_mode:
        num_matches = 0
        pattern = old_calls[offset : offset + largest_match[1] - largest_match[0]]
        for i in range(len(old_calls) - (len(pattern) - 1)):
            for j in range(len(pattern)):
                # compare offset
                if old_calls[i + j][1] != pattern[j][1]:
                    break
                # on match complete (last iteration)
                if j == len(pattern) - 1:
                    num_matches += 1
                    if num_matches > 1:
                        return []
        if num_matches != 1:
            return []
    return largest_match


def do_pattern_based_translation(script_old, script_new, script_name='script', low_accuracy_mode=False):
    old_calls = script_old['calls']
    old_table = script_old['table']
    new_calls = script_new['calls']
    new_table = script_new['table']
    offset = 0
    while offset < len(old_calls):
        found_unmapped = False
        for i in range(len(old_calls) - offset):
            if old_table[old_calls[i + offset][0]] not in generated_translations_rev:
                offset += i
                found_unmapped = True
                break
        if not found_unmapped:
            if offset == 0 and not low_accuracy_mode:
                log("[pattern matching] %s: fully translated" % script_name)
            break
        pattern_coords = generate_pattern(script_old, script_new, offset, low_accuracy_mode)
        if len(pattern_coords) != 0:
            pattern_start = pattern_coords[0]
            pattern_end = pattern_coords[1]
            pattern_len = pattern_end - pattern_start
            old_pattern_start = offset
            old_pattern_end = offset + pattern_len
            if pattern_len > min_pattern_size:
                added_translations = 0
                for j in range(pattern_start, pattern_end):
                    old_native_hash = old_table[old_calls[offset + j - pattern_start][0]]
                    new_native_hash = new_table[new_calls[j][0]]
                    if not new_native_hash in generated_translations:
                        if new_native_hash == 0x6A973569BA094650:
                            log('[pattern matching] WRONG HASH HERE OR SOMETHING')
                        generated_translations[new_native_hash] = old_native_hash
                        generated_translations_rev[old_native_hash] = new_native_hash
                        added_translations += 1
                    elif not low_accuracy_mode and generated_translations[new_native_hash] != old_native_hash:
                        log('[pattern matching] %s: WARNING: inconsistent result for 0x%016X...' % (script_name, new_native_hash))
                if not low_accuracy_mode or added_translations > 0:
                    log('[pattern matching] %s (%d%%): [%d:%d] at %d (%d elements) (+%d, total: %d)' % (script_name, int(old_pattern_end / len(old_calls) * 100), old_pattern_start, old_pattern_end, pattern_start, pattern_len, added_translations, len(generated_translations)))
        offset += 1


log('=> performing dynamic pattern based translation...')

script_keys = list(old_script_data)
for i in range(len(script_keys)):
    if len(new_script_data[script_keys[i]]['calls']) != 0:
        log('[pattern matching] === %s [calls: %d, table: %d] (%d/%d) ===' % (script_keys[i][:-9], len(new_script_data[script_keys[i]]['calls']), len(new_script_data[script_keys[i]]['table']), i+1, len(script_keys)))
        do_pattern_based_translation(old_script_data[script_keys[i]], new_script_data[script_keys[i]], script_keys[i][:-9])


#
# stage 3: parse the old crossmap for reverse lookup
#

old_crossmap_rev = {}
with open(old_crossmap_filename, "r") as cmf:
    line = True
    while line:
        line = cmf.readline()
        hash_tuple = re.findall("0x[0-9A-Fa-f]+", line)
        if len(hash_tuple) < 2:
            continue
        old_crossmap_rev[int(hash_tuple[1], 0)] = int(hash_tuple[0], 0)


#
# stage 4: somehow recover missing entries according to old crossmap
#

# todo: figure out a reliable way to do so as apparently we're still missing hashes even though we've exhausted
#       all the scripts that exist on both old and new releases with call instruction offset delta pattern matching
#       (~5104 stock native translations currently generatable (~7min) from a 5210 desired goal)
#       also, figure out why 0x6A973569BA094650 is wrongly translated according to fivem's universal crossmap


#
# stage 5: universalize and write the translations as the final crossmap
#

generated_crossmap = {}
fc = open(new_crossmap_filename, "w")
for new in generated_translations:
    if generated_translations[new] != new and generated_translations[new] in old_crossmap_rev:
        fc.write("0x%016X, 0x%016X,\n" % (old_crossmap_rev[generated_translations[new]], new))
        generated_crossmap[old_crossmap_rev[generated_translations[new]]] = new
fc.close()

log('[crossmap generator] === wrote a total of %d translations! ===' % len(generated_crossmap))

# debug
wrong_count = 0
with open('1604_crossmap.txt', "r") as cmf:
    line = True
    while line:
        line = cmf.readline()
        hash_tuple = re.findall("0x[0-9A-Fa-f]+", line)
        if len(hash_tuple) < 2:
            continue
        hash_tuple = (int(hash_tuple[0], 0), int(hash_tuple[1], 0))
        if hash_tuple[0] in generated_crossmap:
            if generated_crossmap[hash_tuple[0]] != hash_tuple[1]:
                log('[crossmap verifier] found wrong result on 0x%016X :( (got: 0x%016X, expected: 0x%016X)' % (hash_tuple[0], generated_crossmap[hash_tuple[0]], hash_tuple[1]))
                wrong_count += 1

log('[crossmap verifier] summary: %d/%d (%d%%, %d missing), %d wrong translation(s), %d%% accuracy' % (len(generated_crossmap), len(old_crossmap_rev), (len(generated_crossmap) / len(old_crossmap_rev) * 100), len(old_crossmap_rev) - len(generated_crossmap), wrong_count, ((len(generated_crossmap) - wrong_count) / len(generated_crossmap) * 100)))

logf.close()

from z3 import *
import time

print("Start time: ", time.strftime("%H:%M:%S"))
  
s = Solver()

arr = [BitVec(f"k{i}", 8) for i in range(32)]


for i in range(len(arr)):  
    s.add(Or(  
        And(arr[i] >= BitVecVal(ord('0'), 8), arr[i] <= BitVecVal(ord('9'), 8)),  
        And(arr[i] >= BitVecVal(ord('A'), 8), arr[i] <= BitVecVal(ord('Z'), 8)),  
        And(arr[i] >= BitVecVal(ord('a'), 8), arr[i] <= BitVecVal(ord('z'), 8)),  
        arr[i] == BitVecVal(ord('_'), 8),  
        arr[i] == BitVecVal(ord('$'), 8),
    ))

def extend(a):  
    return ZeroExt(56, a)  # Zero-extend to 64 bits  

for i in range(len(arr)):
    s.add(arr[i] >= 0x20, arr[i] <= 0x7e)

# STAGE 1
KB = (extend(arr[4]) * 0xef7a8c)  
KB += 0x9d865d8d  
KB -= (extend(arr[24]) * 0x45b53c)  
KB += 0x18baee57  
KB -= (extend(arr[0]) * 0xe4cf8b)  
KB -= 0x913fbbde  
KB -= (extend(arr[8]) * 0xf5c990)  
KB += 0x6bfaa656  
KB ^= (extend(arr[20]) * 0x733178)  
KB ^= 0x61e3db3b  
KB ^= (extend(arr[16]) * 0x9a17b8)  
KB -= 0xca2804b1  
KB ^= (extend(arr[12]) * 0x773850)  
KB ^= 0x5a6f68be  
KB ^= (extend(arr[28]) * 0xe21d3d)  
KB ^= 0x5c911d23  
KB += 0x7e9b8587
# STAGE 2  
KB2 = (extend(arr[17]) * 0x99AA81)  
KB2 -= 0x74edea51  
KB2 ^= (extend(arr[5]) * 0x4ABA22)  
KB2 += 0x598015bf  
KB2 ^= (extend(arr[21]) * 0x91A68A)  
KB2 ^= 0x6df18e52  
KB2 ^= (extend(arr[1]) * 0x942FDE)  
KB2 += 0x15c825ee  
KB2 -= (extend(arr[13]) * 0xFE2FBE)  
KB2 += 0xd5682b64  
KB2 -= (extend(arr[29]) * 0xD7E52F)  
KB2 += 0x798bd018  
KB2 ^= (extend(arr[25]) * 0xE44F6A)  
KB2 -= 0xe66d523e  
KB2 += (extend(arr[9]) * 0xAF71D6)  
KB2 += 0x921122d3  
KB2 -= 0xe1148bae
# STAGE 3
KB3 = (extend(arr[10]) * 0x48C500)  
KB3 -= 0x8fdaa1bc  
KB3 -= (extend(arr[30]) * 0x152887)  
KB3 += 0x65f04e48  
KB3 -= (extend(arr[14]) * 0xAA4247)  
KB3 ^= 0x3d63ec69  
KB3 ^= (extend(arr[22]) * 0x38D82D)  
KB3 ^= 0x872eca8f  
KB3 ^= (extend(arr[26]) * 0xF120AC)  
KB3 += 0x803dbdcf  
KB3 += (extend(arr[2]) * 0x254DEF)  
KB3 ^= 0xee380db3  
KB3 ^= (extend(arr[18]) * 0x9EF3E7)  
KB3 -= 0x6deaa90b  
KB3 += (extend(arr[6]) * 0x69C573)  
KB3 -= 0xc9ac5c5d 
KB3 += 0x20c45c0f3
# STAGE 4
KB4 = (extend(arr[11]) * 0x67DDA4)  
KB4 += 0xf4753afc  
KB4 += (extend(arr[31]) * 0x5BB860)  
KB4 ^= 0xc1d47fc9  
KB4 ^= (extend(arr[23]) * 0xAB0CE5)  
KB4 += 0x544ff977  
KB4 += (extend(arr[7]) * 0x148E94)  
KB4 -= 0x9cb3e419  
KB4 -= (extend(arr[15]) * 0x9E06AE)  
KB4 -= 0xadc62064  
KB4 ^= (extend(arr[3]) * 0xFB9DE1)  
KB4 ^= 0x4e3633f7  
KB4 -= (extend(arr[27]) * 0xA8A511)  
KB4 ^= 0xa61f9208  
KB4 += (extend(arr[19]) * 0xD3468D)  
KB4 += 0x4a5d7b48  
KB4 += 0x109bed5e
# Script generated result. Until STAGE 5 it is verified to be correct
KB5 = (extend(arr[12]) * 0x640ba9) + 0x516c7a5c
KB5 = (KB5 - (extend(arr[0]) * 0xf1d9e5)) + 0x8b424d6b
KB5 = (KB5 + (extend(arr[28]) * 0xd3e2f8)) + 0x3802be78
KB5 = (KB5 + (extend(arr[24]) * 0xb558ce)) - 0x33418c8e
KB5 = (KB5 - (extend(arr[8]) * 0x2f03a7)) ^ 0xe050b170
KB5 = (KB5 + (extend(arr[16]) * 0xb8fa61)) ^ 0x1fc22df6
KB5 = (KB5 - (extend(arr[20]) * 0xe0c507)) ^ 0xd8376e57
KB5 = (KB5 + (extend(arr[4]) * 0x8e354e)) - 0x1d3b2c188
KB6 = (extend(arr[17]) * 0xa9b448) ^ 0x9f938499
KB6 = (KB6 + (extend(arr[5]) * 0x906550)) + 0x407021af
KB6 = (KB6 ^ (extend(arr[13]) * 0xaa5ad2)) ^ 0x77cf83a7
KB6 = (KB6 ^ (extend(arr[29]) * 0xc49349)) ^ 0x3067f4e7
KB6 = (KB6 + (extend(arr[9]) * 0x314f8e)) + 0xcd975f3b
KB6 = (KB6 ^ (extend(arr[21]) * 0x81968b)) + 0x893d2e0b
KB6 = (KB6 - (extend(arr[25]) * 0x5ffbac)) ^ 0xf3378e3a
KB6 = (KB6 - (extend(arr[1]) * 0xf63c8e)) - 0x2aa7c3cb8
KB7 = (extend(arr[22]) * 0xa6edf9) ^ 0x77c58017
KB7 = (KB7 - (extend(arr[18]) * 0xe87bf4)) - 0x999bd740
KB7 = (KB7 - (extend(arr[2]) * 0x19864d)) - 0x41884bed
KB7 = (KB7 + (extend(arr[6]) * 0x901524)) ^ 0x247bf095
KB7 = (KB7 ^ (extend(arr[10]) * 0xc897cc)) ^ 0xeff7eea8
KB7 = (KB7 ^ (extend(arr[14]) * 0x731197)) + 0x67a0d262
KB7 = (KB7 + (extend(arr[30]) * 0x5f591c)) + 0x316661f9
KB7 = (KB7 + (extend(arr[26]) * 0x579d0e)) - 0xc4356e67
KB8 = (extend(arr[23]) * 0x9afaf6) ^ 0xdb895413
KB8 = (KB8 + (extend(arr[19]) * 0x7d1a12)) - 0xc679fc44
KB8 = (KB8 + (extend(arr[11]) * 0x4d84b1)) + 0xa30387dc
KB8 = (KB8 - (extend(arr[15]) * 0x552b78)) ^ 0xf54a725e
KB8 = (KB8 ^ (extend(arr[7]) * 0xf372a1)) - 0x4c5103ad
KB8 = (KB8 + (extend(arr[31]) * 0xb40eb5)) ^ 0x16fa70d2
KB8 = (KB8 ^ (extend(arr[3]) * 0x9e5c18)) + 0x38784353
KB8 = (KB8 ^ (extend(arr[27]) * 0xf2513b)) - 0x5fdada18
KB9 = (extend(arr[28]) * 0xac70b9) + 0xdae0a932
KB9 = (KB9 ^ (extend(arr[4]) * 0xc42b6f)) ^ 0xbc03104c
KB9 = (KB9 - (extend(arr[0]) * 0x867193)) + 0xdc48c63a
KB9 = (KB9 - (extend(arr[12]) * 0x6d31fe)) ^ 0x4baeb6d0
KB9 = (KB9 - (extend(arr[16]) * 0xaaae58)) - 0xcd7121f8
KB9 = (KB9 + (extend(arr[20]) * 0x9faa7a)) + 0xbe0a2c9c
KB9 = (KB9 + (extend(arr[24]) * 0x354ac6)) ^ 0xd8ad17f1
KB9 = (KB9 - (extend(arr[8]) * 0x3f2acb)) - 0x2ef2cb51c
KB10 = (extend(arr[29]) * 0xe9d18a) ^ 0xcb5557ea
KB10 = (KB10 ^ (extend(arr[25]) * 0x8aa5b9)) ^ 0x9125a906
KB10 = (KB10 - (extend(arr[17]) * 0x241997)) + 0x6e46fcb8
KB10 = (KB10 + (extend(arr[5]) * 0xe3da0f)) + 0x442800ec
KB10 = (KB10 + (extend(arr[13]) * 0xa5f9eb)) + 0xbde8f9af
KB10 = (KB10 + (extend(arr[21]) * 0xd6e0fb)) - 0xc9d97243
KB10 = (KB10 + (extend(arr[1]) * 0x8dc36e)) + 0xc54b7d21
KB10 = (KB10 ^ (extend(arr[9]) * 0xb072ee)) - 0x2e93af59c
KB11 = (extend(arr[30]) * 0xd14f3e) ^ 0xa06c215b
KB11 = (KB11 - (extend(arr[26]) * 0xc5ecbf)) + 0xb197c5c0
KB11 = (KB11 ^ (extend(arr[6]) * 0x19ff9c)) ^ 0x66e7d06c
KB11 = (KB11 + (extend(arr[2]) * 0xe3288b)) ^ 0x80af4325
KB11 = (KB11 ^ (extend(arr[10]) * 0xcfb18c)) - 0xe13c8393
KB11 = (KB11 ^ (extend(arr[18]) * 0xd208e5)) + 0xf96d2b51
KB11 = (KB11 + (extend(arr[14]) * 0x42240f)) - 0x8732273d
KB11 = (KB11 - (extend(arr[22]) * 0x1c6098)) - 0xdf11dab5
KB12 = (extend(arr[11]) * 0x3768cc) ^ 0x19f61419
KB12 = (KB12 - (extend(arr[3]) * 0x43be16)) + 0x566cc6a8
KB12 = (KB12 ^ (extend(arr[15]) * 0xb7cca5)) + 0x6db0599e
KB12 = (KB12 + (extend(arr[27]) * 0xf6419f)) ^ 0xbd613538
KB12 = (KB12 ^ (extend(arr[19]) * 0xae52fc)) + 0x717a44dd
KB12 = (KB12 - (extend(arr[23]) * 0x5eeb81)) + 0xdd02182d
KB12 = (KB12 ^ (extend(arr[7]) * 0xec1845)) ^ 0xef8e5416
KB12 = (KB12 + (extend(arr[31]) * 0x61a3be)) ^ 0x9288d4fa
KB12 = KB12 - 0x281BDBE05
KB13 = (extend(arr[16]) * 0x336e91) + 0xa1eb20e3
KB13 = (KB13 - (extend(arr[4]) * 0xd45de9)) - 0x381ac71a
KB13 = (KB13 + (extend(arr[8]) * 0x76c8f8)) ^ 0xd8caa2cd
KB13 = (KB13 - (extend(arr[20]) * 0x945339)) + 0x524d7efa
KB13 = (KB13 + (extend(arr[12]) * 0x4474ec)) - 0xe47e82cd
KB13 = (KB13 ^ (extend(arr[0]) * 0x51054f)) ^ 0x3321c9b1
KB13 = (KB13 - (extend(arr[24]) * 0xd7eb3b)) + 0x36f6829d
KB13 = (KB13 - (extend(arr[28]) * 0xad52e1)) ^ 0x6Ce2181A
KB13 = (KB13 + 0xC64BBBD)
KB14 = (extend(arr[29]) * 0x725059) ^ 0xa8b69f6b
KB14 = (KB14 + (extend(arr[17]) * 0x6dcfe7)) ^ 0x653c249a
KB14 = (KB14 + (extend(arr[1]) * 0x8f4c44)) ^ 0x68e87685
KB14 = (KB14 - (extend(arr[9]) * 0xd2f4ce)) - 0x87238dc5
KB14 = (KB14 ^ (extend(arr[13]) * 0xe99d3f)) + 0xed16797a
KB14 = (KB14 + (extend(arr[5]) * 0xada536)) - 0x95a05aa9
KB14 = (KB14 - (extend(arr[25]) * 0xe0b352)) ^ 0x43c00020
KB14 = (KB14 + (extend(arr[21]) * 0x8675b6)) + 0x14892795
KB15 = (extend(arr[2]) * 0x4a5e95) + 0x5ed7a1f1
KB15 = (KB15 + (extend(arr[22]) * 0x3a7b49)) ^ 0x87a91310
KB15 = (KB15 - (extend(arr[6]) * 0xf27038)) ^ 0xf64a0f19
KB15 = (KB15 + (extend(arr[30]) * 0xa187d0)) - 0xbbcc735d
KB15 = (KB15 - (extend(arr[18]) * 0xfc991a)) ^ 0xf9ddd08f
KB15 = (KB15 - (extend(arr[26]) * 0x4e947a)) - 0x59a9172e
KB15 = (KB15 ^ (extend(arr[14]) * 0x324ead)) - 0x969a7a64
KB15 = (KB15 - (extend(arr[10]) * 0x656b1b)) + 0x2ca35df7c
KB16 = (extend(arr[11]) * 0x251b86) + 0xa751192c
KB16 = (KB16 - (extend(arr[7]) * 0x743927)) ^ 0xf851da43
KB16 = (KB16 ^ (extend(arr[31]) * 0x9a3479)) ^ 0x335087a5
KB16 = (KB16 ^ (extend(arr[3]) * 0x778a0d)) ^ 0x4bfd30d3
KB16 = (KB16 - (extend(arr[27]) * 0x7e04b5)) - 0x5d540495
KB16 = (KB16 ^ (extend(arr[19]) * 0xf1c3ee)) + 0x460c48a6
KB16 = (KB16 + (extend(arr[15]) * 0x883b8a)) + 0x7b2ffbdc
KB16 = (KB16 + (extend(arr[23]) * 0x993db1)) - 0x1787d53da
KB17 = (extend(arr[16]) * 0xbae081) + 0x2359766f
KB17 = (KB17 ^ (extend(arr[24]) * 0xc2483b)) + 0xea986a57
KB17 = (KB17 - (extend(arr[28]) * 0x520ee2)) ^ 0xa6ff8114
KB17 = (KB17 + (extend(arr[8]) * 0x9864ba)) + 0x42833507
KB17 = (KB17 - (extend(arr[0]) * 0x7cd278)) ^ 0x360be811
KB17 = (KB17 ^ (extend(arr[4]) * 0xbe6605)) - 0x4c927a8d
KB17 = (KB17 + (extend(arr[20]) * 0x3bd2e8)) + 0xb790cfd3
KB17 = (KB17 - (extend(arr[12]) * 0x548c2b)) - 0x1f72482c6
KB18 = (extend(arr[17]) * 0xfb213b) - 0x6773d643
KB18 = (KB18 ^ (extend(arr[9]) * 0xde6876)) ^ 0x8649fde3
KB18 = (KB18 ^ (extend(arr[29]) * 0x629ff7)) ^ 0xa0eeb203
KB18 = (KB18 - (extend(arr[25]) * 0xdbb107)) ^ 0x94aa6b62
KB18 = (KB18 - (extend(arr[1]) * 0x262675)) - 0xdfcf5488
KB18 = (KB18 + (extend(arr[5]) * 0xd691c5)) - 0x5b3ee746
KB18 = (KB18 - (extend(arr[13]) * 0xcafc93)) - 0x111bde22
KB18 = (KB18 - (extend(arr[21]) * 0x81f945)) + 0x20cb2ed29
KB19 = (extend(arr[10]) * 0x52f44d) ^ 0x33b3d0e4
KB19 = (KB19 ^ (extend(arr[30]) * 0xe6e66e)) - 0x275d79b0
KB19 = (KB19 - (extend(arr[6]) * 0xf98017)) ^ 0x456e6c1d
KB19 = (KB19 - (extend(arr[14]) * 0x34fcb0)) ^ 0x28709cd8
KB19 = (KB19 ^ (extend(arr[2]) * 0x4d8ba9)) + 0xb5482f53
KB19 = (KB19 ^ (extend(arr[18]) * 0x6c7e92)) + 0x2af1d741
KB19 = (KB19 + (extend(arr[22]) * 0xa4711e)) ^ 0x22e79af6
KB19 = (KB19 + (extend(arr[26]) * 0x33d374)) - 0xa4f83f9c
KB20 = (extend(arr[27]) * 0x65ac37) + 0x15e586b0
KB20 = (KB20 ^ (extend(arr[31]) * 0xc6dde0)) ^ 0x2354cad4
KB20 = (KB20 ^ (extend(arr[15]) * 0x154abd)) ^ 0xfee57fd5
KB20 = (KB20 ^ (extend(arr[19]) * 0xa5e467)) + 0x315624ef
KB20 = (KB20 ^ (extend(arr[23]) * 0xb6bed6)) - 0x5285b0a5
KB20 = (KB20 - (extend(arr[7]) * 0x832ae7)) + 0xe961bedd
KB20 = (KB20 + (extend(arr[11]) * 0xc46330)) - 0x4a9e1d65
KB20 = (KB20 ^ (extend(arr[3]) * 0x3f8467)) ^ 0x95a6a1c4
KB20 = (KB20 - 0x1110e3519)
KB21 = (extend(arr[24]) * 0xb74a52) ^ 0x8354d4e8
KB21 = (KB21 ^ (extend(arr[4]) * 0xf22ecd)) - 0x34cbf23b
KB21 = (KB21 + (extend(arr[20]) * 0xbef4be)) ^ 0x60a6c39a
KB21 = (KB21 ^ (extend(arr[8]) * 0x7fe215)) + 0xb14a7317
KB21 = (KB21 - (extend(arr[16]) * 0xdb9f48)) - 0xbca905f2
KB21 = (KB21 - (extend(arr[28]) * 0xbb4276)) - 0x920e2248
KB21 = (KB21 ^ (extend(arr[0]) * 0xa3fbef)) + 0x4c22d2d3
KB21 = (KB21 ^ (extend(arr[12]) * 0xc5e883)) ^ 0x50a6e5c9
KB21 = (KB21 + 0x271a423a)
KB22 = (extend(arr[13]) * 0x4b2d02) ^ 0x4b59b93a
KB22 = (KB22 - (extend(arr[9]) * 0x84bb2c)) ^ 0x42d5652c
KB22 = (KB22 ^ (extend(arr[25]) * 0x6f2d21)) + 0x1020133a
KB22 = (KB22 + (extend(arr[29]) * 0x5fe38f)) - 0x62807b20
KB22 = (KB22 + (extend(arr[21]) * 0xea20a5)) ^ 0x60779ceb
KB22 = (KB22 ^ (extend(arr[17]) * 0x5c17aa)) ^ 0x1aaf8a2d
KB22 = (KB22 - (extend(arr[5]) * 0xb9feb0)) - 0xadbe02fb
KB22 = (KB22 - (extend(arr[1]) * 0x782f79)) + 0xe7b16cc4
KB23 = (extend(arr[6]) * 0x608d19) - 0x2eee62ec
KB23 = (KB23 - (extend(arr[14]) * 0xbe18f4)) ^ 0xb86f9b72
KB23 = (KB23 ^ (extend(arr[30]) * 0x88dec9)) + 0xaf5cd797
KB23 = (KB23 ^ (extend(arr[18]) * 0xb68150)) - 0x3d073ba5
KB23 = (KB23 + (extend(arr[22]) * 0x4d166c)) + 0xbb1e1039
KB23 = (KB23 - (extend(arr[2]) * 0x495e3f)) + 0xe727b98e
KB23 = (KB23 - (extend(arr[10]) * 0x5caba1)) - 0x1a3cf6c1
KB23 = (KB23 + (extend(arr[26]) * 0x183a4d)) - 0x130883afe
KB24 = (extend(arr[11]) * 0xffd0ca) - 0x8f26cee8
KB24 = (KB24 ^ (extend(arr[7]) * 0xbf2b59)) + 0xc76bad6e
KB24 = (KB24 + (extend(arr[23]) * 0x29df01)) + 0xeef034a2
KB24 = (KB24 ^ (extend(arr[27]) * 0xbbda1d)) + 0x5923194e
KB24 = (KB24 - (extend(arr[31]) * 0x5d24a5)) - 0x81100799
KB24 = (KB24 + (extend(arr[15]) * 0x3dc505)) - 0x69baee91
KB24 = (KB24 ^ (extend(arr[19]) * 0x4e25a6)) + 0x2468b30a
KB24 = (KB24 - (extend(arr[3]) * 0xae1920)) ^ 0xd3db6142
KB24 = (KB24 - 0x1BB7aF00F)
# KB25 = (extend(arr[4]) * 0xf56c62) ^ 0x6c7d1f41
# KB25 = (KB25 + (extend(arr[16]) * 0x615605)) + 0x5b52f6ee
# KB25 = (KB25 + (extend(arr[20]) * 0x828456)) ^ 0x6f059759
# KB25 = (KB25 - (extend(arr[28]) * 0x50484b)) + 0x84e222af
# KB25 = (KB25 ^ (extend(arr[8]) * 0x89d640)) + 0xfd21345b
# KB25 = (KB25 - (extend(arr[24]) * 0xe4b191)) + 0xfe15a789
# KB25 = (KB25 ^ (extend(arr[0]) * 0x8c58c1)) ^ 0x4c49099f
# KB25 = (KB25 + (extend(arr[12]) * 0xa13c4c)) ^ 0x3276e75f5
KB26 = (extend(arr[1]) * 0x73aaf0) ^ 0xa04e34f1
KB26 = (KB26 + (extend(arr[29]) * 0xf61e43)) + 0xd09b66f3
KB26 = (KB26 + (extend(arr[25]) * 0x8cb5f0)) + 0xc11c9b4b
KB26 = (KB26 ^ (extend(arr[17]) * 0x4f53a8)) - 0x6465672e
KB26 = (KB26 + (extend(arr[9]) * 0xb2e1fa)) ^ 0x77c07fd8
KB26 = (KB26 - (extend(arr[21]) * 0xb8b7b3)) - 0x882c1521
KB26 = (KB26 + (extend(arr[13]) * 0x13b807)) ^ 0x758dd142
KB26 = (KB26 ^ (extend(arr[5]) * 0xdd40c4)) - 0x1f4f56022
KB27 = (extend(arr[14]) * 0xca894b) + 0xa34fe406
KB27 = (KB27 + (extend(arr[18]) * 0x11552b)) + 0x3764ecd4
KB27 = (KB27 ^ (extend(arr[22]) * 0x7dc36b)) + 0xb45e777b
KB27 = (KB27 ^ (extend(arr[26]) * 0xcec5a6)) ^ 0x2d59bc15
KB27 = (KB27 + (extend(arr[30]) * 0xb6e30d)) ^ 0xfab9788c
KB27 = (KB27 ^ (extend(arr[10]) * 0x859c14)) + 0x41868e54
KB27 = (KB27 + (extend(arr[6]) * 0xd178d3)) + 0x958b0be3
KB27 = (KB27 ^ (extend(arr[2]) * 0x61645c)) - 0x3ddb80073
KB28 = (extend(arr[27]) * 0x7239e9) - 0x760e5ada
KB28 = (KB28 - (extend(arr[3]) * 0xf1c3d1)) - 0xef28a068
KB28 = (KB28 ^ (extend(arr[11]) * 0x1b1367)) ^ 0x31e00d5a
KB28 = (KB28 ^ (extend(arr[19]) * 0x8038b3)) + 0xb5163447
KB28 = (KB28 + (extend(arr[31]) * 0x65fac9)) + 0xe04a889a
KB28 = (KB28 - (extend(arr[23]) * 0xd845ca)) - 0xab7d1c58
KB28 = (KB28 + (extend(arr[15]) * 0xb2bbbc)) ^ 0x3a017b92
KB28 = (KB28 ^ (extend(arr[7]) * 0x33c8bd)) + 0xa31b6a50
KB29 = (extend(arr[0]) * 0x53a4e0) - 0x6061803e
KB29 = (KB29 - (extend(arr[16]) * 0x9bbfda)) + 0x69b383f1
KB29 = (KB29 - (extend(arr[24]) * 0x6b38aa)) - 0x971317a0
KB29 = (KB29 + (extend(arr[20]) * 0x5d266f)) + 0x5a4b0e60
KB29 = (KB29 - (extend(arr[8]) * 0xedc3d3)) ^ 0x93e59af6
KB29 = (KB29 - (extend(arr[4]) * 0xb1f16c)) ^ 0xe8d2b9a9
KB29 = (KB29 + (extend(arr[12]) * 0x1c8e5b)) - 0x68839283
KB29 = (KB29 + (extend(arr[28]) * 0x78f67b)) + 0xbc17051a
KB30 = (extend(arr[17]) * 0x87184c) - 0x72a15ad8
KB30 = (KB30 ^ (extend(arr[25]) * 0xf6372e)) + 0x16ad4f89
KB30 = (KB30 - (extend(arr[21]) * 0xd7355c)) - 0xbb20fe35
KB30 = (KB30 ^ (extend(arr[5]) * 0x471dc1)) ^ 0x572c95f4
KB30 = (KB30 - (extend(arr[1]) * 0x8c4d98)) - 0x94650c74
KB30 = (KB30 - (extend(arr[13]) * 0x5ceea1)) ^ 0xf703dcc1
KB30 = (KB30 - (extend(arr[29]) * 0xeb0863)) + 0xad3bc09d
KB30 = (KB30 ^ (extend(arr[9]) * 0xb6227f)) + 0x87f314d1
KB31 = (extend(arr[30]) * 0x8c6412) ^ 0xc08c361c
KB31 = (KB31 ^ (extend(arr[14]) * 0xb253c4)) + 0x21bb1147
KB31 = (KB31 + (extend(arr[2]) * 0x8f0579)) - 0xfa691186
KB31 = (KB31 - (extend(arr[22]) * 0x7ac48a)) + 0xbb787dd5
KB31 = (KB31 + (extend(arr[10]) * 0x2737e6)) ^ 0xa2bb7683
KB31 = (KB31 - (extend(arr[18]) * 0x4363b9)) ^ 0x88c45378
KB31 = (KB31 ^ (extend(arr[6]) * 0xb38449)) - 0x209dc078
KB31 = (KB31 + (extend(arr[26]) * 0x6e1316)) - 0xd025b63e
# KB32 = (extend(arr[19]) * 0x390b78) + 0x7d5deea4
# KB32 = (KB32 - (extend(arr[15]) * 0x70e6c8)) - 0x6ea339e2
# KB32 = (KB32 ^ (extend(arr[27]) * 0xd8a292)) - 0x288d6ec5
# KB32 = (KB32 - (extend(arr[23]) * 0x978c71)) - 0xe5d85ed8
# KB32 = (KB32 + (extend(arr[31]) * 0x9a14d4)) - 0xb69670cc
# KB32 = (KB32 ^ (extend(arr[7]) * 0x995144)) - 0xd2e77342
# KB32 = (KB32 ^ (extend(arr[11]) * 0x811c39)) - 0x2dd03565
# KB32 = (KB32 ^ (extend(arr[3]) * 0x9953d7)) ^ 0x28bc55a11

s.add(KB == 0x0)
s.add(KB2 == 0x0)
s.add(KB3 == 0x0)
s.add(KB4 == 0x0)
s.add(KB5 == 0x0)
s.add(KB6 == 0x0)
s.add(KB7 == 0x0)
s.add(KB8 == 0x0)
s.add(KB9 == 0x0)
s.add(KB10 == 0x0)
s.add(KB11 == 0x0)
s.add(KB12 == 0x0)
s.add(KB13 == 0x0)
s.add(KB14 == 0x0)
s.add(KB15 == 0x0)
s.add(KB16 == 0x0)
s.add(KB17 == 0x0)
s.add(KB18 == 0x0)
s.add(KB19 == 0x0)
s.add(KB20 == 0x0)
s.add(KB21 == 0x0)
s.add(KB22 == 0x0)
s.add(KB23 == 0x0)
s.add(KB24 == 0x0)
# # s.add(KB25 == 0x0)
s.add(KB26 == 0x0)
s.add(KB27 == 0x0)
s.add(KB28 == 0x0)
s.add(KB29 == 0x0)
s.add(KB30 == 0x0)
s.add(KB31 == 0x0)
# # s.add(KB32 == 0x0)

if s.check() == sat:  
    m = s.model()  
    res = "".join([chr(m[arr[i]].as_long()) for i in range(32)])  
    print("Found solution:", res)  
else:  
    print("No solution found.")  

print("End time: ", time.strftime("%H:%M:%S"))
print("Time taken: ", time.process_time())

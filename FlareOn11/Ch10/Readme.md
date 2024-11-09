# Steps to debug

## use UEFITool

1. Download `UEFITool_NE_A68_win64.zip` from https://github.com/LongSoft/UEFITool/releases
2. Extract `FullShell.efi` *application* from `bios.bin` file
3. Mount the provided disk image and copy `FullShell.efi` application to the disk.
4. Unmount the disk

## Build OVMF in a Linux environment
1. git clone git://github.com/tianocore/edk2.git
2. cd edk2
3. edksetup.sh
4. vim Conf/target.txt
5. Edit the target file as below
```sh
ACTIVE_PLATFORM       = OvmfPkg/OvmfPkgX64.dsc
TOOL_CHAIN_TAG        = GCC5 
TARGET_ARCH           = X64 
TARGET                = DEBUG
```
6. run the command `build`
7. go to build directory and grab OVFM.fd file

## Run with QEMU
1. `qemu-system-x86_64.exe -s -pflash .\FlareOn11\Images\OVMF.fd -hda .\FlareOn11\Images\disk.img -m 1024 -net none -debugcon file:debug.log -global isa-debugcon.iobase=0x402`
2. Notice we specified `debug.log` file this is important
3. After the QEMU boot is complete and you reach the shell prompt in QEMU, open the `debug.log` file scroll to the end and and prepare to monitor for all new lines to come
6. Now in shell type `fs0:`
7. Then type `FullShell.efi`
8. After the `FullShell.efi` is launched there will be a line in `debug.log` something like this:
```log
Loading driver at 0x0003F170000 EntryPoint=0x0003F177B14 FullShell.efi
```
## Debug with IDA
1. Load `FullShell.efi` in IDA pro
2. In debugger menu select `Remote GDB debugger"
3. In `Process Options` specify server to `localhost` and port to `1234` this is where QEMU is listening for debuggger connection
4. Now run. It will say a process is running do you want to attach to it? -- Select `yes`
9. From `Edit` menu in IDA goto `program` and then `Rebase` the program's imagebase at location from `debug.log` file which in this case is *`0x0003F170000`*
10. Set breakpoints and start debuggin

## Check the Scripts folder for the solutions
1. A disassembler
2. Compile assembly to produce 32bit ELF
3. Open in IDA and Decompile
4. Convert to python
5. Brute force and z3

## Example of how a decompiled output from IDA looks like
![image](https://github.com/user-attachments/assets/285dc9a9-9b9c-4cf5-b4f6-6b0748b6b647)


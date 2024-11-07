# Solution

Exception plays not much hinderance and we don't pay too mcuch attention to it in this solution. We will have to use it a little bit while automating.

## Removing the obfuscation while mainitaining executability
The obfuscation is as follow:
Component 1 obfuscation:
1. Whenever it enters a call statement the prologue is a pop instruction that pops (writes) the return address to the epilogue of the function.
2. In the epilogue it adds the return address with an integer value abd puts this at the current esp effectively make this calculated result the return address of the funtion.
We will not touch this pattern while deofucating.
Component 2 obfuscation:
1. After the pop instructions at the prologue the code modifies the bytes that are executed next with actual opcode bytes.
2. It executes those real code bytes
3. Post this actual code bytes are executed it is followed with instruction which destroys the real code bytes again by writing garbage to it.
4. What we will do is when the real code bytes are executed and about to be destroyed again we will overwrite the destroying code bytes with NOP.
5. Since we also don't need the instruction which prepared these real code bytes that were executed before the real code bytes we will NOP them too
This will give us an executable in which we have the actual code or important code that we need for analysis.
We have this script that does this

## Understanding the drama
1. When in unknow teritory and not sure where to start our attention should always be caught by the code that is using the user supplied input (commadline parameter).
2. The fist time where a byte from user imput is used anywhere in a calculation is with `MUL` keyword.
3. Something goes on in between, actually too many things goes on in between but next point of interest is the code site from  where it comes to tell us about whether the key is wrong or right.
4. So, we have a start and end and all we need to do is analyze this code

But the code is still not very staight forward to analyze it from `start` to 'end' in a nice way. What I mean is there are too many calls, hlt etc etc. breaking the flow.
So, What we do?

## Tracing

We throw it in x64dbg. and from preference change the x64dbg to let the PRIV instruction (which hlt is) exeception being handled by the application itself why should we be bothering x64dbg about it.
But, also make a selection in that exception setting window to let it log it. We want to see at what addresses the exception occured.
There is a very nice way to do it in WinDbg using following command but x64dbg is fine ioo.

Copy this list of excpetion address into sumblime or whereever you can use regex based find replace and make it into a list like this `[exr_addr1, exr_addr2,..,exr_addrn]

Okay now there is a code in the executavle that sets up execption handler for the execption that it cause (what a useless thing to do) so that when an execption for those particular addresses (the ones in the list above) happen catch them and handle them.
Make a copy of this logic in IDA python and get those exception handler addresses. All we want is the address that is going to be called next when hlt at a particular address is executed. Make IDA python print it in a way like `bp next_address`
Also let's princt `` same number of times there are items in the list containing exception address

Now paste the output of the python script in the `script` tab of x64dbg.

Now pot a breakpoint in the main() function where the control is transferred into the virtual Memory section. Go to script tab again and go to the last bp <addr> an right click select run until here. 
With the above step done you will have breakpoint set on all the exception handlers. 

Now from the debugger menu setup a trace session, fill out the form for log text and the file name etc to start the tracing. It will start to trace from the beginnng of the Virtual memory until the 1st breakpoint hit.
Now go back to the script tab and point the cursors at the line `` and press spacebar. It will start tracing and might throw some error just ignore the errors and press spacebar again (after dismissing the errors).

In breakpoint tab we will see it moving from top to bottom. Goal is to stop tracing after the last breakpoint at execption handler is exeuted 

Do set the breakpoint on function which prints "wrong key" so that you know the point to stop tracing.

From the trace window. right click and choose export to CSV.


## Excel analysi

Now save the csv as excel and convert it into table.
Filter out all instructions starting with
pop
ret
push
xchg
hlt
nop
anything that that [+28]
anything that only has virtual memory locations for both the operand or if single operand just has the virtual memory location. Don't filter instruction with stack loations

Now the excel will have something like this.

From here it will be easy to understand what's going going on.

## Analysis

1. 8 MUL instruction this corresponds 8 rounds
2. Each Mul is used with a key byte. This will give you the constant and the postion of the key byte in the commadline string we passed
3. Except for the MUL result from the first round you will notice that the MUL result is tranformed using ADD, SUB or XOR
4. Just after this transformation you will see the tranformed value being changed byte by byte.
5. The above change is based on the value of the calculated result in step 3.
6. The change is REPLACE and ADD / SUB  and repeat this for all bytes REPLACE -> ADD / SUB -> REPLACE -> ADD / SUB as seen in screenshot below:
7. From step 7 we get the operation that is being applied to transformed value in step 3. We will call this result the tranformed value 2 or previous product
8. This previous product is then used in next round.

We implemet this understand in python in this script:

Now You will notice the add or xub is done using 1





The program has a very consistent patte

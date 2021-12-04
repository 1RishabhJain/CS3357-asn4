# CS3357-asn4
 
**Purpose of the Assignment**

The general purpose of this assignment is to continue to explore network programming and principles of reliable data transfer, leveraging the chat client and server constructed for Assignment #2 and used again in Assignment #3.  This assignment is designed to give you further experience in:

- writing networked applications
- the socket API in Python
- creating UDP applications 
- techniques for reliable data transfer

**Assigned**

Wednesday, November 10, 2021 (please check the main [course website](http://owl.uwo.ca) regularly for any updates or revisions)

**Due**

The assignment is due Wednesday, December 8th, 2021 by 11:55pm (midnight-ish) through an electronic submission through the [OWL site](http://owl.uwo.ca). If you require assistance, help is available online through [OWL](http://owl.uwo.ca).

**Late Penalty**

Late assignments will be accepted for up to two days after the due date, with weekends counting as a single day; the late penalty is 20% of the available marks per day. Lateness is based on the time the assignment is submitted.

**Individual Effort**

Your assignment is expected to be an individual effort. Feel free to discuss ideas with others in the class; however, your assignment submission must be your own work. If it is determined that you are guilty of cheating on the assignment, you could receive a grade of zero with a notice of this offence submitted to the Dean of your home faculty for inclusion in your academic record.

**What to Hand in**

Your assignment submission, as noted above, will be electronically through [OWL](http://owl.uwo.ca).  You are to submit all Python files required for your assignment.   If any special instructions are required to run your submission, be sure to include a README file documenting details.  (Keep in mind that if the TA cannot run your assignment, it becomes much harder to assign it a grade.)

**Assignment Task**

You are required to take your TCP-based chat client and server from Assignment #3 and replace its use of TCP with UDP.  In the process, you are to implement a reliable data transfer protocol on top of UDP to ensure that your application can tolerate lost and corrupted packets.  As a result, you will need to provide additional code for error detection, retransmission, and timeouts.

For this assignment, your chat client and server must support the stop-and-wait reliability protocol (RDT 3.0) discussed in class and in the course textbook. This means that you do not need to buffer more than one outstanding packet at a time. When a packet is sent, you wait for it to be acknowledged before returning to allow the program to send another packet. This means you will need to add a sequence number and acknowledgement fields to data being transmitted, and implement the necessary support functionality as discussed in the lecture materials.  For your reference, the finite state machines for the protocol are included below.

**RDT Sender:**

**RDT Receiver:**

Please note that the receiver diagram included above technically corresponds to RDT 2.2, but it required no extensions to work for RDT 3.0.

**Some Particulars**

Here are some specific requirements and other important notes: 

- The same chat functionality, including following and file attachments, from Assignment #3 is required for this assignment.  Please refer back to the specification for Assignment #3 for more detail.  
- In addition to sending data, to support reliability, you will need to include things like sequence numbers, acknowledgement numbers, checksums, and more.    (Please refer to lecture materials on the RDT 3.0 reliability protocol for details.)  How do you package all of that along with your data?  If everything was text, in theory you could package this as additional text with the messages, but this won't work in general.  Particularly when working with files with binary data.  
- To support packing up your data with the additional data fields needed by the protocol, you should use [Python structs](https://docs.python.org/3/library/struct.html).  They provide mechanisms to pack and unpack data into structures that can be sent and received in single units.  Once packed, you can compute MD5 checksums using the [Python hashlib](https://docs.python.org/3/library/hashlib.html) library.  As a reference, a simple UDP packet client and server are attached to this assignment.  This sample code demonstrates the use of structs and checksums on both the sending and receiving ends.  Note that the packet structure used may need to be modified for this assignment, and you might need to make other adjustments as needed to support the data requirements for things.  Regardless, this provides a good starting point for this aspect of the assignment.
- To assist in the process, you will want to create new send and receive functions and encapsulate all RDT functionality into those functions.  That will make things easier to drop into an existing code base without disturbing existing application functionality already in place.  That might not cover everything needed to support reliability, but it should help with most things.  (For example, you could create a new send() function that packs your data, checksums it, sends it along, and then doesn't return until the data has been acknowledged successfully.)
- To help manage timeouts, likely the most straightforward way is to leverage the use of [Python selectors](https://docs.python.org/3/library/selectors.html), as we've already been using those in earlier assignments.  Interestingly, the select() function supports an optional timeout that you can use to help detect missing acknowledgements.  (A fixed timeout of 1 or 2 seconds is likely sufficient, but feel free to pick something else that is appropriate.)  There are of course other ways of doing this, but this is at least one that you are already familiar with.  You will have to be careful with choosing when to block and when not to block, but you are already familiar with this as well.
- To test your program, you need a way to insert errors into your packets, and to periodically drop packets.  If only someone could create some kind of a tool or simulator for UDP to do this sort of thing?  Oh wait, I already did.  And you used it as part of Assignment #1.  Yes, this means it's must time again!  You can use its various options to inject errors (avoid setting the rate higher than 0.0001 for a bit error rate of 0.0001%) and to lose  packets ( I would not set it much higher than 10% or 20%).  If you crank those options too high, it will be hard to get data through and you're making life unnecessarily difficult.  For instructions on how to use must and for code, please refer to Assignment #1.  (Also, remember that a slightly updated version was posted under our Announcements.)
- To make your life easier, take a very incremental approach to doing things.  Do not use must at first, as it might complicate things.  Start by just creating your packet structures, sending them, receiving them, and unpacking them on the other side, without worrying about any reliability protocol.  (There is no point in complicating things if the packet structures cannot be moved around on their own!)  After this, add the error detection functionality and test it by injecting errors with must.  Next, add retransmission functionality, and test that it works using must.  After this, add the loss handling capabilities as well and again test it with must.  In essence, taking a step-by-step approach similar to how we refined the RDT protocol in class is a good idea. If you do too much at once, and then run into troubles, it will be much harder to tell where you went wrong!

You are to provide all of the Python code for this assignment yourself, except for the sample code attached to this assignment and code used from the Assignment #3 implementation provided to you.  (You can also reuse your own Assignment #3 code as well.)  You are **not** allowed to use Python functions to execute other programs for you, nor are you allowed to use any libraries that haven't been explicitly allowed.  (If there is a particular library you would like to use/import, you must check first.)   All server code files must begin with *server* and* all client files must begin with *client*.  All of these files must be submitted with your assignment.  

As an important note, marks will be allocated for code style. This includes appropriate use of comments and indentation for readability, plus good naming conventions for variables, constants, and functions. Your code should also be well structured (i.e. not all in the main function). 

Please remember to test your program as well, since marks will obviously be given for correctness!  You should send a variety of messages and transfer several different files, including both text and binary files.   You can then use diff to compare the original files and the downloaded files to ensure the correct operation of your client and server.  You should also test out the various ! commands to make sure they work correctly too.  Don't forget to test things using must as noted above, creating errors and losing packets, to ensure your reliability protocol is working correctly despite network conditions that are not ideal.  


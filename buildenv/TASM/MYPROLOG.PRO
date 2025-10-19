/* MYPROLOG.PRO */

global predicates
   double(integer,integer) - (i,o) language asm

goal
   write("Enter an integer "),
   readint(I),
   double(I,Y),
   write(I," doubled is ",Y) ,
   readchar(_).

 
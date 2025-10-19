/* ADDPRO.PRO */

global predicates
   add(integer,integer,integer) - (i,i,o),(i,o,i),(o,i,i)
                                  language asm

goal
   add(2,3,X), write("2 + 3 = ",X),nl,
   add(2,Y,5), write("5 - 2 = ",Y),nl,
   add(Z,3,5), write("5 - 3 = ",Z),nl,
   readchar(_).
 
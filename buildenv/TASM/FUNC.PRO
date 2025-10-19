
/* FUNC.PRO */

global domains
   ifunc = int(integer)

global predicates
   makeifunc(integer,ifunc) - (i,o) language c

goal
   makeifunc(4,H),
   write(H),
   readchar(_).

 
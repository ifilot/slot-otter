
#include <stdio.h>

int  main(void)

{
   int  TestValue;

   scanf("%d",&TestValue);          /* get the value to increment*/
   asm  inc  WORD PTR TestValue;    /* increment it (inassembler) */
   printf("%d",TestValue);          /* print the incremented value */
}

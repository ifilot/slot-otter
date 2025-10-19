char * TestString="Line 1\nline 2\nline 3";
extern unsigned int LineCount(char * StringToCount,
       unsigned int * CharacterCountPtr);
main()
{
   unsigned int LCount;
   unsigned int CCount;
   LCount = LineCount(TestString, &CCount);
   printf("Lines: %d\nCharacters: %d\n", LCount, CCount);
}

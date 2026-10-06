/* Shared option parser body: instantiate once with near or far linkage.
 * Kept common so exhaustive host parser tests cover the installer too. */
PORT_SCOPE int PORT_CALL PORT_PARSE(const char *s, U16 *result) {
    U16 value=0, digit;
    int any=0;
    while (*s==' ' || (*s>='\t' && *s<='\r')) ++s;
    if (*s=='+') ++s;
    if (s[0]=='0' && (s[1]=='x' || s[1]=='X')) s+=2;
    while (*s) {
        if (*s>='0' && *s<='9') digit=*s-'0';
        else if (*s>='a' && *s<='f') digit=*s-'a'+10;
        else if (*s>='A' && *s<='F') digit=*s-'A'+10;
        else return 0;
        /* Check BEFORE shifting: Turbo C's unsigned int is only 16 bits. */
        if (value>0x0fff) return 0;
        value=(value<<4)|digit; any=1; ++s;
    }
    if (!any || value<0x100 || value>0xfffc || (value&3)) return 0;
    *result=value; return 1;
}
PORT_SCOPE void PORT_CALL PORT_UPPER(char *s) {
    for (;*s;++s) if (*s>='a' && *s<='z') *s-=32;
}

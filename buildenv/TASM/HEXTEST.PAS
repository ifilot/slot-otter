program HexTest;
var
  num : word;

{$F+}

function HexStr (var num; byteCount : byte) : string; external;

{$L HEXSTR.OBJ}

{$F-}
begin
  num := $face;
  Writeln('The Converted Hex String is "',HexStr(num,sizeof(num)),'"');
end.

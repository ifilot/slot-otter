program EnvTest;
{ program looks for environment strings }

var
  EnvVariable : string;
  EnvValue : string;

{$F+}

function EnvString(s:string) : string; external;
{$L ENVSTR.OBJ}
{$F-}
begin
  EnvVariable := 'PROMPT';
  EnvValue := EnvString(EnvVariable);
  if EnvValue='' then EnvValue := '*** not found ***';
  Writeln('Environment Variable: ',EnvVariable,'  Value: ',EnvValue);
end.

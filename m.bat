echo off

rem  the path of the git command


	set git = D:\Git\bin\git.exe

	set d=%date:~0,2%
	set mo=%date:~3,2%
	set y=%date:~6,4%
	set h=%time:~0,2%
	set mi=%time:~3,2%

	set upinfo = %y%_%mo%_%d%_%h%_%mi%

	git add *

	REM delay 3 second
	TIMEOUT /T 3	 
	git commit -m  "update by likui"
	REM delay 5 second
	TIMEOUT /T 5	
	git push

	git status

pause

@echo off


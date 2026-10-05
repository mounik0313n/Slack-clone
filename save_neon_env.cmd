@echo off
set "NEON_DATABASE_URL=postgresql://neondb_owner:npg_hGvgInA8weC7@ep-winter-mud-b38thd3f-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
setx NEON_DATABASE_URL "%NEON_DATABASE_URL%"
set "DATABASE_URL=%NEON_DATABASE_URL%"
setx DATABASE_URL "%DATABASE_URL%"
echo Stored Neon values in user environment.

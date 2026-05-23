FROM nginx:1.27-alpine

RUN printf '%s\n' \
	'<!doctype html>' \
	'<html lang="en">' \
	'  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>Grand Opening Radar</title></head>' \
	'  <body style="font-family: Georgia, serif; max-width: 760px; margin: 40px auto; line-height: 1.5;">' \
	'    <h1>Grand Opening Radar</h1>' \
	'    <p>Phase 0 placeholder frontend is running in Docker.</p>' \
	'  </body>' \
	'</html>' \
	> /usr/share/nginx/html/index.html

EXPOSE 80


files=d3.v3.min.js prelude-browser-min.js					\
	arc.js editme.js post.js bg.js						\
	arccn.css index.html							\
	apply-text.png cpiks_logo_eng.png done-text.png apply.png server.png	\
	map.png

all: $(files)

dist:
	mkdir -p dist
	cp $(files) dist


.PHONY: dist

%.css: %.less
	lessc $< $@

%.js:	%.ls
	livescript -c $<


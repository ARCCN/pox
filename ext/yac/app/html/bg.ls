require! _: \prelude-ls

# Background map
addMap = (sel) ->
  sel .append \image
     .attr \xlink:href, 'map.png'
     .attr \width, width
     .attr \height, height
     .attr \x, -25



# QR code
addQR = (sel) ->
  s = Config.qr-size
  margin = 10

  sel .append \foreignObject .attr \id, \qr
    .attr \width, s .attr \height, s
    .attr \x, width - s - margin
    .attr \y, height - s - margin

  new QRCode \qr,
    text: Config.qr-text, width: s, height: s,
    colorLight: \transparent, colorDark: 'grey' #'#CECECE' #'#4978DE'


# Current configuration table
addTable = (sel) ->
  [w,h] = [92,160]

  e = sel. append \foreignObject .classed \table, true
      .classed \btn, true
      .attr \width, w .attr \height, h
      .attr \x, width - w - 30
      .attr \y, 0.1*height

  t = e. append \xhtml:table

  c = [for x in comp-names
        for y in comp-names
         when x != y
           [ [x, y], (.length) <| path-nodes x, y ] ]
      |> _.concat |> _.concat

  for [[a,b], v] in c
    tr = t.append \tr
    let th = (tr .append \th)
     let add = ((s) -> let c = computers-by-name[s]
                         th .append \span .text _.take 1, c.name
                            .style \color, c.color)
      add a
      th .append \span .text '–'
      add b
    tr .append \td .text '·'
    tr .append \td .text v



export BG = { addMap, addQR, addTable }

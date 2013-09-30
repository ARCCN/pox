
require! _: \prelude-ls;

export const width = 0.9 * document.width - 10
export const height = document.height - 220


@nodes = [];
@links = [];

export const comp-names = <[A B C]>
const comp-name-pairs = _.zip comp-names, (_.tail comp-names ++ _.head comp-names)

path-src = (path) -> path?[0]
path-dst = (path) -> path?[1]

@path-hops = (src, dst) ->
  _.filter ((n) -> [src,dst] === [path-src(n.path), path-dst(n.path)]), nodes

@path-nodes = (src, dst) -> [src] ++ (path-hops src, dst) ++ [dst]


@computers = Config.computers

@current-configuration = ->
  for a in [1 to 3]
    for b in [1 to 3]
      when a !== b
        [ "#{a}, #{b}", (path-nodes computers[a-1].id, computers[b-1].id).length ]
  |> _.concat
  |> _.pairs-to-obj
  |> -> 'pair_map': it


new-id = do ->
  id = 1000
  -> 'e' + id++


@force = d3.layout.force()
    .nodes(nodes)
    .links(links)
    .charge Config.hopCharge
    .linkDistance (d) -> Config.linkDistance(d, width)
    .size([width, height])
    .gravity(0.02)
    .on(\tick, tick)
    .linkStrength 0.9
#    .theta 0.1
    .friction 0.9




svg = d3.selectAll \.canvas .append \svg:svg
  .attr \class, \well
  .attr \width, width
  .attr \height, height


# Layers
svg .append \g .classed \z-map, true
svg .append \g .classed \z-links, true
svg .append \g .classed \z-nodes, true
svg .append \g .classed \z-infos, true


@node = svg.select \.z-nodes .selectAll \g.node
@link = svg.select \.z-links .selectAll \.link




new-hop = (path, x=null, y=null, id=newId()) ->
  id: id, path: path, x: x, y: y, xxx: Math.random()

new-link = (src, dst, path) ->
  source:src, target:dst, path: path, count: path[2]



@computers-by-name = {}

for [c,id] in _.zip computers, comp-names
  c.fixed = true
  c.computer = true
  [x,y] = c.xy; c.x = x * width; c.y = y * height
  c.id = id
  computers-by-name[c.id] = c
  c.xxx = Math.random()

# Add hops
do ->
  add = (src, dst, n, k) ->
    path = [src.id, dst.id, k]
    ns = [new-hop path for i from 1 to n]

    nsa = [src] ++ ns ++ [dst]

    _.each (x) -> (nodes.push x), ns
    _.zip-with (x,y) -> (links.push(new-link x, y, path)), nsa, _.tail nsa

  cfg = Config.startingConfig

  {'A-B':[ab,ba], 'B-C':[bc,cb], 'C-A':[ca,ac]} = cfg

  for a-b in _.keys cfg
    [null, fromc, toc] = a-b.match /(\w)-(\w)/
    [ab,ba] = cfg[a-b]
    add computers-by-name[fromc], computers-by-name[toc], ab, 1
    add computers-by-name[toc], computers-by-name[fromc], ba, 2

# … and computers
for c in computers
  nodes.push c



# Add arrow-end <svg:marker>s
for c in computers
  svg.append \svg:defs .append \svg:marker
     .attr \id, "arrow-#{c.id}"
     .attr \viewBox, '0 -5 15 10'
     .attr \refX, 20
     .attr \orient, \auto

     .append \svg:path
     .attr \d, 'M0,-5 L15,0L0,5'
     .attr \stroke, c.color
     .attr \stroke-width, '6px'
     .attr \fill, \transparent



# Add computer icon re-coloring <svg:filter>s
for c in computers
  [r,g,b] = (_.map (-> parseInt(it) / 255) <| _.tail <| c.color.match /rgb\((\d+),\s*(\d+),\s*(\d+)\)/)

  filt = svg.append \svg:defs .append \filter
         .attr \id "colorize-#{c.id}"

  # C_in M = C_out
  # where C_in,C_out are [r g b α 1]^T
  # We replace colours with our (r,g,b) and keep the α
  m = [[0 0 0 0 r]
       [0 0 0 0 g]
       [0 0 0 0 b]
       [0 0 0 1 0]]

  filt .append \feColorMatrix
       .attr \color-interpolation-filters, 'sRGB'
       .attr \type, \matrix
       .attr \values (m |> _.concat |> _.unwords)



BG.addMap (svg.select \.z-map)
BG.addQR (svg.select \.z-map)


redraw {}
setTimeout (-> post \quiet), 0

info-svg = null


# Computer info boxes
do ->
  e = svg .select \.z-infos .selectAll '.info'
    .data computers, (d) -> "info-#{d.id}"
    .enter() .append \g
    .attr \data-id, (d) -> d.id
    .attr \class, \info
    .append \svg:foreignObject
    .attr \width, 300
    .attr \height, 80

  info-svg := e

  div = e.append \xhtml:div .classed \btn, true
  div.append \p .classed 'name', true .text (-> "#{it.name}")
  div.append \p .classed 'ip', true .text (-> "#{it.addr}")



index = (xs, f) ->
  for i in [0 to xs.length]
    when f xs[i]
      return i
  return -1


function add-hop d
    console.log 'ADD', d.path

    [x,y] = d3.mouse this

    nodes.unshift (new-hop d.path, x, y)

    console.log d.path

    links.splice (index links, (==d)), 1

    links.push((new-link d.source, nodes[0], d.path),
               (new-link nodes[0], d.target, d.path))


function hip-hop d, ev
    if d.computer 
       return

    hs = path-hops (path-src d.path), (path-dst d.path)
    if hs.length == 1
       return

    console.log 'HIP', d.path

    i = index nodes, (==d)
    nodes.splice(i, 1)

    a = index links, -> it.source.id == d.id
    to = links[a].target
    links.splice(a, 1);

    b = index links, -> it.target.id == d.id
    from = links[b].source
    links.splice(b, 1)

    links.push (new-link from, to, d.path);



function redraw ev
  console.log 'redraw';

  svg .select \.table .remove!
  BG.addTable (svg.select \.z-map)


  @link := link.data force.links(),
                     (d) -> "#{d.source.id}-#{d.target.id}-#{d.count}"

  link.enter().insert \line, '.node' .attr \class, \link
    .style \marker-end, (d) -> "url(\#arrow-#{path-src d.path})"
    .style \stroke,     (d) -> computers-by-name[path-src d.path].color
    .on \mouseup, (d) ->
       add-hop.call this, d, ev
       redraw ev
       true

  link.exit!remove!

  @node := node.data force.nodes(), (.id)

  enter = node
    .enter()
    .append \g
    .classed \node, true
    .classed \computer, (.computer)

  enter
    .filter (d) -> not d.computer
    .attr \width, 32
    .attr \height, 32
    .append \circle .attr \r, 9

  computer = enter .filter (.computer)
  csize = Config.computerSize

  computer
    .append \circle .attr \r, csize / 1.2
    .classed \undercomp, true
    .attr \fill, (.color)

  computer
    .append \image
    .attr \xlink:href, 'server.png'
    .attr \x, -csize
    .attr \y, -csize
    .attr \width, csize*2
    .attr \height, csize*2
    .attr \filter, (c) -> "url(\#colorize-#{c.id})"

  computer .call force.drag

  node.on \click, (d) ->
    hip-hop.call this, d, ev
    redraw ev

  node.exit!remove!

  force.start!


function hypot (x,y)
  Math.sqrt(x*x, y*y)


svg-translate = (x, y) -> "translate(#{x}, #{y})"
svg-move-arc = (x1,y1,x2,y2,r,sweep) -> "M#{x1},#{y1} A#{r},#{r} 0 0,#{sweep} #{x2},#{y2}"
  

# Every tick
function tick
  margin = 10
  bounded = (max, x) --> _.min (max - margin - 1) <| _.max margin <| x

  x-bounded = bounded width
  y-bounded = bounded height

  node.attr \ignore, (d) ->
    const ds = Config.info-box-offsets
    d3.select(".info[data-id=#{d.id}]")
      .attr \transform, (d) -> let [dx,dy] = ds[d.id]
                                 svg-translate d.x - dx, d.y - dy
    null

  link.attr \x1, (d) -> x-bounded d.source.x
      .attr \y1, (d) -> y-bounded d.source.y
      .attr \x2, (d) -> x-bounded d.target.x
      .attr \y2, (d) -> y-bounded d.target.y

  node.attr \transform, -> svg-translate (x-bounded it.x), (y-bounded it.y)


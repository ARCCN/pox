
var Config = {

  computers: [
    {name: 'Moscow',
     addr: '10.0.2.10',
     xy: [0.55, 0.17], color: 'rgb(220,50,47)'},

    {name: 'San Francisco',
     addr: '10.0.1.10',
     xy: [0.21, 0.277], color: 'rgb(108,113,196)'},

    {name: 'Canberra',
     addr: '10.0.3.10',
     xy: [0.77, 0.666], color: 'rgb(64,173,0)'}
  ],


  startingConfig: { 'A-B': [1,1], 'B-C': [1,3], 'C-A': [2,2] },

  infoBoxOffsets: { 'A': [-50,70], 'B': [190,10], 'C': [-20,88] },
      
  postTo: '/arccn/post/',

  qrText: 'https://github.com/ARCCN/pox/tree/betta/ext/yac',
  qrSize: 120,


  computerSize: 42,
  hopCharge: -300,
  linkDistance: function (d, width) { return width / 20 * (1 + d.source.xxx) }

};



function post (quiet)
{
  console.log('post');

  var cc = currentConfiguration();

  var ajax = d3.xhr (Config.postTo, 'application/json');

  if (! quiet)
  {
    var around = d3.select('.around-app');
    var onclick = around.attr('onclick');

    ajax.on ('load',
	     function () {
	       around.classed('done', true).attr('onclick', '');
	       setTimeout (function () { around.classed('done', false).attr('onclick', onclick) },
			   1000);
	     });
  }

  var data = JSON.stringify (cc);
  console.log ('post', data);

  ajax.post (data);
}



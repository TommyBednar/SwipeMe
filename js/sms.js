//I'll need a function to call on click of "update"
//It'll need to do an AJAX request and grab the list of messages for both chat boxes

function refresh()
    {
      $.ajax({
          type: "GET",
          url: "../mock/data",
          dataType: "json"
        })
      .done(function(data){
        if (data)
        {
          console.log("We got JSON")
          console.log(data)
          //console.log(data.charAt(0))
          window.test=data;
        }

        var buyerDiv = $('#buyer_stream')
        buyerDiv.empty()
        buyerDiv.append('<ul><li>Something</li><li>Another thing</li></ul')
        /*for (tuple in data.buyer_messages)
        {
        	var 
        	$buyer.append(tuple[])
        }*/
      });
    }
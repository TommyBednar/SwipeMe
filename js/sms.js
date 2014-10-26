//I'll need a function to call on click of "update"
//It'll need to do an AJAX request and grab the list of messages for both chat boxes

function del()
{
	$.ajax({
		  type: "DELETE",
		  url: "/mock/data",
	});
}

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
	        var buyerDiv = $('#buyer_stream')
	        buyerDiv.empty()
	        console.log(data['buyer_list'])
	        //buyerDiv.append('<ul><li>Something</li><li>Another thing</li></ul')
	        for (index in data['buyer_list'])
	        { 
	        	console.log(data['buyer_list'][index])
	        	buyerDiv.append('<p>' + data['buyer_list'][index][0] + '\tStatus: ' + data['buyer_list'][index][1] + '</p>')
	        }

	        var sellerDiv = $('#seller_stream')
	        sellerDiv.empty()
	        for (index in data['seller_list'])
	        { 
	        	console.log(data['seller_list'][index])
	        	sellerDiv.append('<p>' + data['seller_list'][index][0] + '\tStatus: ' + data['seller_list'][index][1] + '</p>')
	        }
        /*
          
          //console.log(data.charAt(0))
          window.test=data;
        */
        }

        
      });
    }

function send(type)
{
	var div = null
	var sms = null

	if (type === 'buyer')
	{
		div = $('#buyer_stream')
		sms = $('#buyer_sms').val()
	}
	else if (type == 'seller')
	{
		div = $('#seller_stream')
		sms = $('#seller_sms').val()
	}

	data = JSON.stringify({ 'sms':sms, 'customer_type':type })
	console.log(data)
	//buyerDiv.append(string)
	$.ajax({
		  type: "POST",
		  url: "/mock/data",
		  data: data,
		  dataType: "application/JSON"
	});
}


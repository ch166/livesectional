function get_badge(ap,loc) {
  var xhttp = new XMLHttpRequest();
  var outp = "";
  var vis_in_miles = "";
  var sky_condition = "";
  var sky_ceiling = "";
  var flightcategory = "VFR";
  var metar = "";
  
  xhttp.onreadystatechange = function() {
  if (this.status == 404) {
    console.log('Undefined Airport');
    metar = 'The Airport ID entered is Undefined. Please Check ID';
    flightcategory = "UNDF";
  }

  if (this.readyState == 4 && this.status == 200) {
    // console.log(xhttp.responseText); 
    
    obj = JSON.parse(xhttp.responseText);
    metar = obj.metar;
    flightcategory = obj.flightcategory;
    if (metar == "") {
      metar = "No METAR Data Returned by FAA API. CLICK for Raw METAR"; 
      flightcategory = "NOWX";
    }

    // console.log(metar);
    // console.log(flightcategory);                         

  }
      
  outp = '<a href="https://www.aviationweather.gov/metar/data?ids='+ap+'&format=decoded&hours=0&taf=on&layout=on" target="_blank">';
  if (flightcategory == 'VFR') {
    var outp = outp + '<h6><span class="badge badge-success">';
    } else if (flightcategory == 'MVFR') {
    var outp = outp + '<h6><span class="badge badge-primary">';
    } else if (flightcategory == 'IFR') {
    var outp = outp + '<h6><span class="badge badge-danger">';
    } else if (flightcategory == 'LIFR') {
    var outp = outp + '<h6><span class="badge-lifr">';
    } else if (flightcategory == 'NOWX') {
    var outp = outp + '<h6><span class="badge-nowx">';
    } else if (flightcategory == 'UNDF') {
    var outp = outp + '<h6><span class="badge-undf">';
    }    

  outp = outp + '&nbsp'+flightcategory+'&nbsp</span>&nbsp-&nbsp'+metar+'</h6></a>';        
  document.getElementById(loc).innerHTML = outp;                         
};
    
xhttp.open("GET", "/wx/"+ap, true);
xhttp.send();
}

 
<!-- Script to grab Flight Category from www.checkwx.com. Limited number of hits per day. Must in HEAD-->
function get_fc(ap,loc) {
  var xhttp = new XMLHttpRequest();
  var outp = ""

  xhttp.onreadystatechange = function() {
  if (this.readyState == 4 && this.status == 200) {
    // console.log(xhttp.responseText);
    obj = JSON.parse(xhttp.responseText);

      if (obj.data[0].flight_category == 'VFR') {
        var outp = '<a href="https://www.checkwx.com/weather/'+ap+'/metar" target="_blank"><h5><p class="badge badge-success">'
        } else if (obj.data[0].flight_category == 'MVFR') {
        var outp = '<a href="https://www.checkwx.com/weather/'+ap+'/metar" target="_blank"><h5><p class="badge badge-primary">'
        } else if (obj.data[0].flight_category == 'IFR') {
        var outp = '<a href="https://www.checkwx.com/weather/'+ap+'/metar" target="_blank"><h5><p class="badge badge-danger">'
        } else if (obj.data[0].flight_category == 'LIFR') {
        var outp = '<a href="https://www.checkwx.com/weather/'+ap+'/metar" target="_blank"><h5><p class="badge badge-warning">'
        }
      outp = outp + '&nbsp'+obj.data[0].flight_category+'&nbsp</p></h5></a>'
    document.getElementById(loc).innerHTML = outp
  }
};

xhttp.open("GET", "/wx/"+ap, true);
xhttp.send();
}


<!-- Script to grab raw METAR data only from api.weather.gov-->    
function get_raw(ap,loc) {
  var xhttp = new XMLHttpRequest();
  var outp = ""
  
  xhttp.onreadystatechange = function() {
  if (this.readyState == 4 && this.status == 200) {
    // console.log(xhttp.responseText);      
    obj = JSON.parse(xhttp.responseText); 
    // console.log(obj.properties.metar);      
    document.getElementById(loc).innerHTML = obj.metar       
  }
};
    
xhttp.open("GET", "/wx/"+ap, true);
xhttp.send();
}


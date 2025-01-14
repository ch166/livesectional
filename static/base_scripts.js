function get_badge(ap, loc) {
    let xhttp = new XMLHttpRequest();
    let outp = '';
    let obj = '';
    let vis_in_miles = '';
    let sky_condition = '';
    let sky_ceiling = '';
    let flightcategory = 'VFR';
    let metar = '';

    xhttp.onreadystatechange = function () {
        if (this.status === 404) {
            // console.log('Undefined Airport')
            metar = 'The Airport ID entered is Undefined. Please Check ID'
            flightcategory = 'UNDF'
        }

        if (this.readyState === 4 && this.status === 200) {
            // console.log(xhttp.responseText);
            obj = JSON.parse(xhttp.responseText)
            metar = obj.metar
            flightcategory = obj.flightcategory
            if (metar === '') {
                metar = 'No METAR Data Returned by API. CLICK for Raw METAR'
                flightcategory = 'NOWX'
            }
            // console.log(metar);
            // console.log(flightcategory);
        }

        outp =
            '<a href="https://www.aviationweather.gov/data/metar?ids=' +
            ap +
            '&hours=0&decoded=yes&include_taf=yes" target="_blank">'
        if (flightcategory === 'VFR') {
            outp = outp + '<h6><span class="badge-vfr">'
        } else if (flightcategory === 'MVFR') {
            outp = outp + '<h6><span class="badge-mvfr">'
        } else if (flightcategory === 'IFR') {
            outp = outp + '<h6><span class="badge-ifr">'
        } else if (flightcategory === 'LIFR') {
            outp = outp + '<h6><span class="badge-lifr">'
        } else if (flightcategory === 'NOWX') {
            outp = outp + '<h6><span class="badge-nowx">'
        } else if (flightcategory === 'UNDF') {
            outp = outp + '<h6><span class="badge-undf">'
        }
        outp =
            outp +
            '&nbsp' +
            flightcategory +
            '&nbsp</span>&nbsp-&nbsp' +
            metar +
            '</h></a>'
        document.getElementById(loc).innerHTML = outp
    }
    xhttp.open('GET', '/wx/' + ap, true)
    xhttp.send()
}

// -- Script to grab flightcategory from local endpoint
function get_fc(ap, loc) {
    let xhttp = new XMLHttpRequest();
    let outp = '';
    let obj = '';

    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            // console.log(xhttp.responseText);
            obj = JSON.parse(xhttp.responseText)

            if (obj.data[0].flight_category === 'VFR') {
                outp =
                    '<a href="https://www.checkwx.com/weather/' +
                    ap +
                    '/metar" target="_blank"><h5><p class="badge-vfr">'
            } else if (obj.data[0].flight_category === 'MVFR') {
                outp =
                    '<a href="https://www.checkwx.com/weather/' +
                    ap +
                    '/metar" target="_blank"><h5><p class="badge-mvfr">'
            } else if (obj.data[0].flight_category === 'IFR') {
                outp =
                    '<a href="https://www.checkwx.com/weather/' +
                    ap +
                    '/metar" target="_blank"><h5><p class="badge-ifr">'
            } else if (obj.data[0].flight_category === 'LIFR') {
                outp =
                    '<a href="https://www.checkwx.com/weather/' +
                    ap +
                    '/metar" target="_blank"><h5><p class="badge-lifr">'
            }
            outp = outp + '&nbsp' + obj.data[0].flight_category + '&nbsp</p></h5></a>'
            document.getElementById(loc).innerHTML = outp
        }
    }
    xhttp.open('GET', '/wx/' + ap, true)
    xhttp.send()
}

// -- Script to grab raw METAR local endpoint
function get_raw(ap, loc) {
    let xhttp = new XMLHttpRequest();
    let outp = '';
    let obj = '';

    xhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            // console.log(xhttp.responseText);
            obj = JSON.parse(xhttp.responseText)
            // console.log(obj.properties.metar);
            document.getElementById(loc).innerHTML = obj.metar
        }
    }
    xhttp.open('GET', '/wx/' + ap, true)
    xhttp.send()
}

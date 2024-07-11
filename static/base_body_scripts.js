let coll = document.getElementsByClassName('collapsible');
let i;

for (i = 0; i < coll.length; i++) {
    coll[i].addEventListener('click', function () {
        this.classList.toggle('active')
        let content = this.nextElementSibling;
        if (content.style.maxHeight) {
            content.style.maxHeight = null
        } else {
            content.style.maxHeight = content.scrollHeight + 'px'
        }
    })
}

const $dropdown = $('.dropdown')
const $dropdownToggle = $('.dropdown-toggle')
const $dropdownMenu = $('.dropdown-menu')
const showClass = 'show'

$(window).on('load resize', function () {
    if (this.matchMedia('(min-width: 768px)').matches) {
        $dropdown.hover(
            function () {
                const $this = $(this)
                $this.addClass(showClass)
                $this.find($dropdownToggle).attr('aria-expanded', 'true')
                $this.find($dropdownMenu).addClass(showClass)
            },
            function () {
                const $this = $(this)
                $this.removeClass(showClass)
                $this.find($dropdownToggle).attr('aria-expanded', 'false')
                $this.find($dropdownMenu).removeClass(showClass)
            }
        )
    } else {
        $dropdown.off('mouseenter mouseleave')
    }
})

function myFunction(selectObject) {
    let myString = selectObject.name;
    let myArray = myString.split('/')
    let num = myArray[0]
    let icao = myArray[1]
    let field = myArray[2]
    let x = selectObject.value;

    if (x.length !== 4) {
        window.alert('You Must Enter 4 Char Airport ID, NULL or LGND')
        document.getElementById(icao).focus()
        return
    }

    if (x === 'NULL') {
        document.getElementById(field).innerHTML =
            'LED will be turned off, set to: ' + x
    } else if (x === 'LGND') {
        document.getElementById(field).innerHTML =
            'LED will be used as a Legend, set to; ' + x
    } else {
        document.getElementById(field).innerHTML =
            '<a href=https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId=' +
            x +
            ' target=' +
            '_blank' +
            '>You entered: ' +
            x +
            '. Click for more info.</a>'
    }

    document.getElementsByName('lednum')[0].value = num
    //    document.forms["ledonoff"].submit();//
}

function checkBlankF(selectObject) {
    let myString = selectObject.name
    console.log(myString)
    let x = selectObject.value
    console.log(x)

    if (x.length === 0) {
        window.alert('You Must Enter a Value.\n It cannot be left blank.')
        if (myString === 'rev_rgb_grb') {
            selectObject.value = '[]'
        } else if (myString === 'exclusive_list') {
            selectObject.value = '[]'
        } else if (myString === 'welcome') {
            selectObject.value = '"Welcome to LiveSectional V4"'
        } else if (myString === 'morse_msg') {
            selectObject.value = '"LiveSectional"'
        } else {
            selectObject.value = 0
        }

    }
}

function upperCaseF(a) {
    setTimeout(function () {
        a.value = a.value.toUpperCase()
    }, 1)
}

function scrollto() {
    // Scroll to myNavbar - an ID in base_lite.html
    let elmnt = document.getElementById('myNavbar')
    elmnt.scrollIntoView()
}

function fillinledonoff(selectObject) {
    let myString = selectObject.name
    let myArray = myString.split('/')
    let num = myArray[0]
    document.getElementsByName('lednum')[0].value = num
}

function get_metar(ap, loc) {
    let xmlhttp = new XMLHttpRequest()

    xmlhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            let result = this.responseText.substring(1, this.responseText.length - 1);
            let myObj = JSON.parse(result);
            document.getElementById(loc).innerHTML = myObj.report
        }
    }

    xmlhttp.open(
        'GET',
        'https://navlost.eu/api/reports/metar/' + ap + '?format=application/json',
        true
    )
    xmlhttp.send()
}

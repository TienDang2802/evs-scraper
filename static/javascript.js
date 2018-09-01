function updateSlider(val) {
    document.getElementById("demo").innerHTML = val;
    document.getElementById("demo2").innerHTML = val
    document.getElementById("demo3").innerHTML = val / 10;
}

function toggler(divId) {
    $("#" + divId).toggle();
}

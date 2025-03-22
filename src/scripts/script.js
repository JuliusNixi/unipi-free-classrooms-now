const API_URL = "http://localhost:8080/api/"

function getPolesData() {
    const POLES_URL = API_URL + "poles_data"
    
    fetch(POLES_URL)
        .then(response => response.json())
            .then(data => {
                let unordered = document.getElementsByTagName("ul")[0]
                let poles_data_list = data["poles_data"]
                poles_data_list.forEach(pole_obj => {
                    let li = document.createElement("li")

                    let a = document.createElement("a")
                    a.href = Object.values(pole_obj)[0]
                    a.textContent = Object.keys(pole_obj)[0]

                    li.appendChild(a)

                    unordered.appendChild(li)
                });
            })
    .catch(error => console.error(error))
}


document.addEventListener("DOMContentLoaded", function() {
    getPolesData()
});

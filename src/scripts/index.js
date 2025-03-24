const API_URL = "http://193.123.60.3:54321/api/"

function getPolesData() {
    const POLES_DATA_URL = API_URL + "poles_data"
    
    fetch(POLES_DATA_URL)
        .then(response => response.json())
            .then(data => {
                let unordered_list = document.getElementsByTagName("ul")[0]

                let poles_data_list = data["poles_data"]
                if (poles_data_list === undefined) {
                    console.error('Error in getting data inside the APIs.');
                    let p_error = document.getElementsByTagName("p")[0]
                    p_error.textContent = "Errore nel reperire i dati all'interno delle APIs."
                    return
                }

                poles_data_list.forEach(pole_obj => {
                    let li = document.createElement("li")

                    let a = document.createElement("a")
                    // Sanitize the pole name.
                    let pole_name = Object.keys(pole_obj)[0].toLowerCase().trim()
                    a.href = "/polo.html?polo=" + pole_name
                    // Make the first letter uppercase.
                    a.textContent = pole_name.charAt(0).toUpperCase() + pole_name.slice(1)

                    li.appendChild(a)

                    unordered_list.appendChild(li)
                });
            })
    .catch(error => {
        console.error('Error in fetching APIs:', error);
        let p_error = document.getElementsByTagName("p")[0]
        p_error.textContent = "Errore nel contattare le APIs."
    })
}

document.addEventListener("DOMContentLoaded", function() {
    getPolesData()
});

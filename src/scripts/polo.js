const API_URL = "https://vps.giulionisi.me:54321/api/"

// Return all the rooms given a pole name.
async function getAllRooms(pole_name) {
    const ALL_ROOMS_URL = API_URL + "all_rooms_given_pole" + "?pole_name=" + pole_name

    let all_rooms = []
    
    await fetch(ALL_ROOMS_URL)
        .then(response => response.json())
            .then(data => {

                let all_rooms_data_list = data["all_rooms"]
                if (all_rooms_data_list === undefined) {
                    console.error('Error in getting data inside the APIs.');
                    let p_error = document.getElementsByTagName("p")[0]
                    p_error.textContent = "Errore nel reperire i dati all'interno delle APIs."
                    return
                }

                all_rooms_data_list.forEach(room => {
                    all_rooms.push(room["Classroom"])
                });
            })
    .catch(error => {
        console.error('Error in fetching APIs:', error);
        let p_error = document.getElementsByTagName("p")[0]
        p_error.textContent = "Errore nel contattare le APIs."
    })

    return all_rooms

}

function getFreeClassrooms(all_rooms, pole_name) {

    const FREE_CLASSROOMS_URL = API_URL + "free_classrooms_given_pole" + "?pole_name=" + pole_name

    fetch(FREE_CLASSROOMS_URL)
        .then(response => response.json())
            .then(data => {

                let free_classrooms_data_list = data["free_classrooms"]
                if (free_classrooms_data_list === undefined) {
                    console.error('Error in getting data inside the APIs.');
                    let p_error = document.getElementsByTagName("p")[0]
                    p_error.textContent = "Errore nel reperire i dati all'interno delle APIs."
                    return
                }

                // Filling the list with all the rooms, assuming they are all busy.
                let lis = []
                all_rooms.forEach(room => {
                    let li = document.createElement("li")
                    li.textContent = room + " - ❌"
                    lis.push(li)
                })

                // Updating the list with the free rooms.
                free_classrooms_data_list.forEach(free_classroom => {
                    for (let i = 0; i < lis.length; i++) {
                        if (lis[i].textContent.includes(free_classroom["Classroom"])) {
                            lis[i].textContent = lis[i].textContent.replace(" - ❌", "") + " - ✅"
                            if (free_classroom["NextStartTime"] !== undefined) {
                                lis[i].textContent += " Fino alle: " + free_classroom["NextStartTime"].split(" ")[1] + "."
                            }
                            break
                        }
                    }
                });

                let ul = document.getElementsByTagName("ul")[0]
                lis.forEach(li => {
                    ul.appendChild(li)
                });
                
            })
    .catch(error => {
        console.error('Error in fetching APIs:', error);
        let p_error = document.getElementsByTagName("p")[0]
        p_error.textContent = "Errore nel contattare le APIs."
    })

}

document.addEventListener("DOMContentLoaded", async function() {

    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const pole_name = urlParams.get('polo');
    if (pole_name === null) {
        console.error('Error in getting pole name param from the user url request.');
        let p_error = document.getElementsByTagName("p")[0]
        p_error.textContent = "Errore nel reperire il nome del polo dalla tua richiesta."
        return
    }

    let all_rooms = await getAllRooms(pole_name)
    getFreeClassrooms(all_rooms, pole_name)

});

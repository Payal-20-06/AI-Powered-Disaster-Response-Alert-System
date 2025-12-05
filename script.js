// ------------------ BUTTONS & SECTIONS ------------------
const alertBtn = document.getElementById('alert1');
const shelterBtn = document.getElementById('shltr');
const alertsSection = document.getElementById('alertsSection');
const shelterSection = document.getElementById('shelterSection');
const resourceSection = document.getElementById('Resource');

// Initially show Resource Tracking only
resourceSection.style.display = 'block';
alertsSection.style.display = 'none';
shelterSection.style.display = 'none';

// ------------------ ALERTS ------------------
async function loadAlerts() {
    try {
        const res = await fetch("/api/v1/alerts");
        const data = await res.json();
        if(data.success) {
            if(data.alerts.length === 0){
                alertsSection.innerHTML = "<p>No active alerts</p>";
                return;
            }
            alertsSection.innerHTML = data.alerts.map(a => `
                <div class="alert-item">
                    <h4>${a.title} (${a.severity.toUpperCase()})</h4>
                    <p>${a.message}</p>
                    <p><b>Location:</b> ${a.location || 'N/A'}</p>
                </div>
            `).join('');
        }
    } catch(err) {
        console.error(err);
        alertsSection.innerHTML = "<p>Error loading alerts</p>";
    }
}

// Click Alert
alertBtn.addEventListener('click', () => {
    alertsSection.style.display = 'block';
    shelterSection.style.display = 'none';
    loadAlerts();
    alertsSection.scrollIntoView({behavior: "smooth"});
});

// ------------------ SHELTERS ------------------
async function loadShelters() {
    try {
        const res = await fetch("/api/v1/shelters");
        const data = await res.json();
        if(data.success) {
            if(data.shelters.length === 0){
                shelterSection.innerHTML = "<p>No shelters available</p>";
                return;
            }

            const sheltersHTML = data.shelters.map(s => `
                <div class="shelter">
                    <div class="shelt">
                        <i class="fa-solid fa-building-columns fa-beat-fade fa-2x"></i>
                        <div class="h3">
                            <h3>${s.name}</h3>
                            <h5>${s.location?.address || 'N/A'}</h5>
                        </div>
                        <button class="${s.available_capacity > 0 ? 'avail' : 'availmt'}">
                            ${s.available_capacity > 0 ? 'available' : 'full'}
                        </button>
                    </div>
                    <div class="data">
                        <div>Capacity <br> <b>${s.capacity}</b></div>
                        <div class="mid">Occupied <br> <b>${s.current_occupancy}</b></div>
                        <div>Distance <br> <b>${s.distance_km || '-'}</b></div>
                    </div>
                    <div class="prcnt">
                        <p>${Math.round((s.current_occupancy/s.capacity)*100)}% occupied</p>
                        <button class="dir"><i class="fa-regular fa-compass fa-spin fa-spin-reverse"></i> Get Direction</button>
                    </div>
                    <b>Emergency no.: ${s.contact || 'N/A'}</b>
                </div>
            `).join('');
            shelterSection.innerHTML = `<div class="Main2">${sheltersHTML}</div>`;
        }
    } catch(err) {
        console.error(err);
        shelterSection.innerHTML = "<p>Error loading shelters</p>";
    }
}

// Click Shelter
shelterBtn.addEventListener('click', () => {
    shelterSection.style.display = 'block';
    alertsSection.style.display = 'none';
    loadShelters();
    shelterSection.scrollIntoView({behavior: "smooth"});
});

// ------------------ MAP INITIALIZATION ------------------
const map = L.map('mapContainer')?.setView([20, 77], 5); // center India
if(map) {
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
    }).addTo(map);

    // Load shelters as markers
    fetch("/api/v1/shelters")
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                data.shelters.forEach(s => {
                    if(s.location){
                        const lat = parseFloat(s.location.latitude);
                        const lon = parseFloat(s.location.longitude);
                        if(!isNaN(lat) && !isNaN(lon)){
                            L.marker([lat, lon])
                                .addTo(map)
                                .bindPopup(`<b>${s.name}</b><br>Capacity: ${s.capacity}<br>Occupied: ${s.current_occupancy}`);
                        }
                    }
                });
            }
        }).catch(console.error);
}

// ------------------ CITY AUTOCOMPLETE ------------------
const apiKey = "10de3aba21950854d0bd4448f8fddb60"; // OpenWeatherMap
let currentMarker = null;

async function getRecommendations() {
    const query = document.getElementById("cityInput").value.trim();
    const resultsBox = document.getElementById("results");

    if(query.length < 2){
        resultsBox.style.display = "none";
        resultsBox.innerHTML = "";
        return;
    }

    const url = `https://api.openweathermap.org/geo/1.0/direct?q=${query}&limit=5&appid=${apiKey}`;

    try {
        const response = await fetch(url);
        const data = await response.json();
        resultsBox.innerHTML = "";
        resultsBox.style.display = "block";

        if(data.length === 0){
            resultsBox.innerHTML = `<li class="list-group-item">No results found</li>`;
            return;
        }

        data.forEach(city => {
            const li = document.createElement("li");
            li.classList.add("list-group-item");
            li.style.cursor = "pointer";
            li.textContent = `${city.name}, ${city.country}`;
            li.onclick = () => {
                document.getElementById("cityInput").value = city.name;
                resultsBox.style.display = "none";

                // Show map marker at city coordinates
                const coords = [city.lat, city.lon];
                if(currentMarker) map.removeLayer(currentMarker);
                currentMarker = L.marker(coords).addTo(map);
                currentMarker.bindPopup(`${city.name}`).openPopup();
                map.setView(coords, 10);
            };
            resultsBox.appendChild(li);
        });
    } catch(err){
        console.error(err);
        resultsBox.innerHTML = `<li class="list-group-item text-danger">Error fetching data</li>`;
        resultsBox.style.display = "block";
    }
}

// ------------------ LOGIN / SIGNUP ------------------
const loginBox = document.getElementById("loginBox");
const signupBox = document.getElementById("signupBox");
const showSignup = document.getElementById("showSignup");
const showLogin = document.getElementById("showLogin");

showSignup?.addEventListener("click", () => {
    loginBox.style.display = "none";
    signupBox.style.display = "block";
});

showLogin?.addEventListener("click", () => {
    signupBox.style.display = "none";
    loginBox.style.display = "block";
});

// Login with backend
document.querySelector("#loginBox .btn")?.addEventListener("click", async () => {
    const email = loginBox.querySelector('input[type="email"]').value;
    const password = loginBox.querySelector('input[type="password"]').value;

    try {
        const formData = new FormData();
        formData.append("username", email);
        formData.append("password", password);

        const res = await fetch("/login", {
            method: "POST",
            body: formData,
        });

        if(res.redirected){
            window.location.href = res.url;
        } else {
            alert("Invalid username or password");
        }
    } catch(err){
        console.error(err);
        alert("Login error");
    }
});
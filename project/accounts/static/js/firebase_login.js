// -------------------------------
// Firebase Imports
// -------------------------------
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.11.0/firebase-app.js";
import { 
    getAuth, 
    signInWithEmailAndPassword 
} from "https://www.gstatic.com/firebasejs/12.11.0/firebase-auth.js";


// -------------------------------
// Firebase Config
// -------------------------------
// -------------------------------
// Firebase Config (Loaded Safely)
// -------------------------------
let auth;

fetch("/static/config/firebase_auth.json")
    .then(res => res.json())
    .then(firebaseConfig => {
        const app = initializeApp(firebaseConfig);
        auth = getAuth(app);
    })
    .catch(err => {
        console.error("Failed to load Firebase config:", err);
    });
// -------------------------------
// Friendly Error Messages
// -------------------------------
function getFirebaseErrorMessage(error) {
    const messages = {
        "auth/invalid-credential": "Incorrect email or password.",
        "auth/user-not-found": "No account found with this email.",
        "auth/wrong-password": "Incorrect password.",
        "auth/invalid-email": "Please enter a valid email address.",
        "auth/too-many-requests": "Too many failed attempts. Try again later.",
        "auth/network-request-failed": "Network error. Check your connection."
    };

    return messages[error.code] || "Something went wrong. Please try again.";
}


// -------------------------------
// Login Function
// -------------------------------
window.firebaseLogin = function () {
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    signInWithEmailAndPassword(auth, email, password)
    .then(userCred => userCred.user.getIdToken())
    .then(idToken => {
        return fetch("/accounts/auth/firebase/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": window.CSRF_TOKEN
            },
            body: JSON.stringify({ token: idToken })
        });
    })
    .then(async res => {
        // If Django returns an error (403, 400, etc.)
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error);
        }

        // If Django returns success
        return res.json();
    })
    .then(data => {
        showToast("Login successful!", "success");
        setTimeout(() => {
            window.location.href = data.redirect;
        }, 800);
    })
    .catch(err => {
        // If Firebase error → use Firebase messages
        if (err.code) {
            showToast(getFirebaseErrorMessage(err), "error");
        } 
        // If Django error → use Django message
        else {
            showToast(err.message, "error");
        }
    });
};

function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = "toast " + type;
    toast.style.display = "block";

    setTimeout(() => {
        toast.style.display = "none";
    }, 3000);
}
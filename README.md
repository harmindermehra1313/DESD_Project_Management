# DESP_Project_Management

hmmmmmm tasty testing always works

# Docker install

#pull main from git
git pull https://github.com/harmindermehra1313/DESP_Project_Management main


#created django - shouldnt need to be ran again

docker compose run web django-admin startproject placeholder .


#created DB tables in django - shouldnt need to be ran again

docker compose run web python manage.py migrate


#go into the Docker folder and type this into the terminal

docker compose up
BRISTOL REGIONAL FOOD SYSTEM

**Note Hannah:** moved Docker in to correct project folder. Make sure Docker Desktop is open and you can use the following cheat sheet:

### Start containers
docker-compose up

### Start and rebuild
docker-compose up --build

### Run in background
docker-compose up -d

### Stop containers
docker-compose down

### See running containers
docker ps



# [KAN-21] Setting up django apps according to test cases
- Basic Apps created.

- Made a shared templates base (one navbar for everything).
    - `templates/base.html`
- Created a simple app just for general pages (Homepage).
    - App Name: `home`
- Created HTML placeholders for the apps.
  - For each app modified/created:
    - `views.py`
    - `urls.py`
    - `app_name/templates/app_name/index.html`

- Best Practices Followed:
  - Template Inheritance for consistent UIs.
  - Named URL reversing instead of hardcoded paths for maintainability.
  - Namespacing URLs per app to prevent collisions as project grows.
  - Modular URL routing with `include()` for project organisation and keep routing changes localised.
  - Keeping views simple and aligned with templates.
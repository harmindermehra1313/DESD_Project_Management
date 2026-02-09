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

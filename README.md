загружаем в docker на сервере: docker load -i docsearch-app.tar  
проверяем что он полностью перенесен: docker images | grep docsearch
запускаем docker compose up -d
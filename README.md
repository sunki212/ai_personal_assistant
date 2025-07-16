# ai_personal_assistant

Промежуточный выриант проекта

# Примерная структура

ai_personal_assistant/  
│  
├── data_base/  
│ ├── Dockerfile   
│ ├── db_create.py   
│ ├── init.sql   
│ └── utils.py  
│  
├── LLM_settings/  
│ ├── handlers/  
│ ├──── handlers.py  
│ ├──── owner_handlers.py  
│ └──── request_handler.py   
│ │  
│ ├── lists_of_users/  
│ ├──── admitted.json  
│ ├──── applications.json  
│ ├──── blacklist.json  
│ └──── create_JSON_lists.py  
│ │  
│ ├── generate.py   
│ ├── keyboards.py   
│ └── models.py   
│  
├── config/  
│ ├── config.py  
│ └── requirements.txt  
│  
└── README.md # Краткое описание проекта

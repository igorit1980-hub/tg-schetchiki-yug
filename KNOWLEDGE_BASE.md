# Knowledge Base

Эта папка и документы фиксируют единую базу знаний для связки:

- сайт `Счетчики Юг`
- `Битрикс24`
- Telegram-витрина / Telegram-канал

Цель базы знаний:

- иметь один канонический идентификатор товара: `xml_id`
- понимать, какие данные являются мастер-данными сайта
- понимать, какие данные управляются из `Битрикс24`
- иметь готовые правила двустороннего обращения к данным через единый слой интеграции

Структура:

- [knowledge-base/README.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/README.md)
- [knowledge-base/canonical-model.json](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/canonical-model.json)
- [knowledge-base/bitrix24-config.json](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/bitrix24-config.json)
- [knowledge-base/site-catalog-config.json](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/site-catalog-config.json)
- [knowledge-base/sync-workflows.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/sync-workflows.md)
- [knowledge-base/storefront-contract.json](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/storefront-contract.json)
- [knowledge-base/customer-sync.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/customer-sync.md)
- [knowledge-base/bitrix24-customer-fields.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/bitrix24-customer-fields.md)
- [knowledge-base/customer-api-contract.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/customer-api-contract.md)
- [knowledge-base/bitrix24-customer-fields-copy-paste.md](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/knowledge-base/bitrix24-customer-fields-copy-paste.md)

Главный принцип:

- сайт является мастер-источником каталога и товарных карточек
- `Битрикс24` является мастер-источником витринных подборок, акций и менеджерской ответственности
- `Битрикс24` является мастер-источником статуса клиента, карты клиента и разрешенного типа цены
- Telegram читает только уже собранную витринную JSON-модель

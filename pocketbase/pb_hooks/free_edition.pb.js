/// <reference path="../pb_data/types.d.ts" />
// TogetherForever: бесплатная сборка. Всё, что в оригинале открывала покупка
// TogetherForever+, на этом сервере открыто каждому — флаг `plus` ставится
// сам при регистрации и не снимается. Клиент всё равно считает Плюс
// включённым; флаг нужен серверным проверкам (виджеты, анимации).

onRecordCreate((e) => {
  e.record.set("plus", true);
  e.next();
}, "users");

onRecordUpdate((e) => {
  e.record.set("plus", true);
  e.next();
}, "users");

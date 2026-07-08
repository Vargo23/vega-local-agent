# Coordinator Review Gate

Этот блок используется после каждого завершенного этапа.

## Назначение

Coordinator Review Gate нужен, чтобы VEGA не шла дальше по инерции и не накапливала ошибки.

## Проверка

Перед переходом к следующему блоку ответь:

```text
[REVIEW]
Block: <номер или название>
Task match: yes/no
Architecture match: yes/no
Unnecessary complexity: yes/no
Missing parts: none/list
Risks: none/list
Decision: accepted/rework
```

## Decision: accepted

Используй, если блок можно считать готовым.

```text
[DONE] Block <номер> готов. Можно переходить к следующему блоку.
```

## Decision: rework

Используй, если блок требует исправления.

```text
[REWORK] Block <номер> отправлен на переработку.
Reason: <конкретная причина>
Next action: <что исправить>
```

## Правило честности

Если блок не был проверен запуском, не писать "проверено запуском".

Правильно:

```text
[WARNING] Код логически проверен, но не запускался в окружении.
```

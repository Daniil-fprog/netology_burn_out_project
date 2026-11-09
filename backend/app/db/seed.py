from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.note import NoteModel
from app.models.recommendation import RecommendationModel
from app.models.user import UserModel
from app.models.role import RoleModel, UserRoleModel
from app.schemas.common import RoleCode
from app.services.sentiment_service import calculate_confidence


TEST_USER_ID = 1
TEST_USER_NAME = "Даниил"


def seed_roles(db: Session) -> None:
    names = {
        RoleCode.TEACHER: "Преподаватель",
        RoleCode.DIRECTOR: "Директор",
        RoleCode.HEAD: "Глава",
        RoleCode.GROUP_HEAD: "Глава группы",
        RoleCode.SYSTEM_ADMIN: "Системный администратор",
    }
    for code, name in names.items():
        if db.query(RoleModel).filter_by(code=code.value).first() is None:
            db.add(RoleModel(code=code.value, name=name))
    db.commit()


def seed_admin_user(db: Session) -> UserModel:
    """
    Создаёт пользователя-админа Даниил, если его нет.
    """
    user = db.query(UserModel).filter(UserModel.phone == "+79807057002").first()

    if user:
        role = db.query(RoleModel).filter_by(code=RoleCode.SYSTEM_ADMIN.value).one()
        if db.query(UserRoleModel).filter_by(user_id=user.id, role_id=role.id).first() is None:
            db.add(UserRoleModel(user_id=user.id, role_id=role.id))
            db.commit()
        print("Seed: пользователь Даниил уже существует")
        return user

    user = UserModel(
        name="Даниил",
        login="daniil",
        phone="+79807057002",
        password_hash=hash_password("admin123"),
    )

    db.add(user)
    db.flush()
    role = db.query(RoleModel).filter_by(code=RoleCode.SYSTEM_ADMIN.value).one()
    db.add(UserRoleModel(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)

    print(f"Seed: создан пользователь Даниил (id={user.id})")
    return user


def seed_test_data(db: Session) -> None:
    """
    Заполняет БД тестовыми данными:
    - 20 рекомендаций
    - 20 записей для пользователя Даниил
    """

    user = db.query(UserModel).filter(UserModel.phone == "+79807057002").first()

    if user is None:
        print("Seed: пользователь Даниил не найден, тестовые записи не созданы")
        return

    seed_recommendations(db)
    seed_notes_for_user(db, user.id)


def seed_recommendations(db: Session) -> None:
    existing_count = db.query(RecommendationModel).count()

    if existing_count >= 20:
        print("Seed: рекомендации уже есть, пропускаем")
        return

    recommendations = [
        RecommendationModel(
            rec_name="Дыхание 5 минут",
            rec_text="Сделайте несколько медленных вдохов и выдохов, чтобы снизить напряжение.",
            mood_type="negative",
            score_from=0,
            score_to=25,
        ),
        RecommendationModel(
            rec_name="Тёплый чай и пауза",
            rec_text="Сделайте короткую паузу, выпейте чай и дайте себе немного восстановиться.",
            mood_type="negative",
            score_from=0,
            score_to=30,
        ),
        RecommendationModel(
            rec_name="Прогулка 15 минут",
            rec_text="Небольшая прогулка поможет переключиться и снизить уровень тревоги.",
            mood_type="negative",
            score_from=15,
            score_to=40,
        ),
        RecommendationModel(
            rec_name="Послушать спокойную музыку",
            rec_text="Включите спокойный плейлист, чтобы мягко стабилизировать настроение.",
            mood_type="negative",
            score_from=20,
            score_to=45,
        ),
        RecommendationModel(
            rec_name="Записать мысли",
            rec_text="Попробуйте выписать всё, что беспокоит, без оценки и критики.",
            mood_type="negative",
            score_from=20,
            score_to=50,
        ),
        RecommendationModel(
            rec_name="Покушать",
            rec_text="Если вы давно не ели, сделайте нормальный приём пищи или лёгкий перекус.",
            mood_type="neutral",
            score_from=30,
            score_to=60,
        ),
        RecommendationModel(
            rec_name="Лёгкая уборка",
            rec_text="Наведите порядок на рабочем месте, чтобы снизить ощущение хаоса.",
            mood_type="neutral",
            score_from=35,
            score_to=60,
        ),
        RecommendationModel(
            rec_name="Чтение книги",
            rec_text="Почитайте книгу 20–30 минут, чтобы переключиться и восстановить фокус.",
            mood_type="neutral",
            score_from=40,
            score_to=70,
        ),
        RecommendationModel(
            rec_name="Планирование дня",
            rec_text="Запишите 2–3 главные задачи, чтобы вернуть ощущение контроля.",
            mood_type="neutral",
            score_from=45,
            score_to=70,
        ),
        RecommendationModel(
            rec_name="Созвон с близким человеком",
            rec_text="Поговорите с человеком, которому доверяете, чтобы почувствовать поддержку.",
            mood_type="neutral",
            score_from=45,
            score_to=75,
        ),
        RecommendationModel(
            rec_name="Общение с друзьями",
            rec_text="Напишите друзьям или договоритесь о встрече, если хочется живого общения.",
            mood_type="positive",
            score_from=55,
            score_to=85,
        ),
        RecommendationModel(
            rec_name="Спорт",
            rec_text="Сделайте тренировку или лёгкую разминку, чтобы поднять уровень энергии.",
            mood_type="positive",
            score_from=55,
            score_to=90,
        ),
        RecommendationModel(
            rec_name="Прогулка в новом месте",
            rec_text="Смените обстановку и прогуляйтесь там, где давно не были.",
            mood_type="positive",
            score_from=60,
            score_to=90,
        ),
        RecommendationModel(
            rec_name="Послушать любимую музыку",
            rec_text="Включите музыку, которая обычно заряжает вас энергией.",
            mood_type="positive",
            score_from=60,
            score_to=100,
        ),
        RecommendationModel(
            rec_name="Посмотреть фильм",
            rec_text="Выберите лёгкий фильм или сериал, чтобы приятно провести вечер.",
            mood_type="neutral",
            score_from=50,
            score_to=80,
        ),
        RecommendationModel(
            rec_name="Сходить на концерт",
            rec_text="Если есть силы и желание, выберите живое событие для новых эмоций.",
            mood_type="positive",
            score_from=70,
            score_to=100,
        ),
        RecommendationModel(
            rec_name="Сделать фото дня",
            rec_text="Зафиксируйте приятный момент дня, чтобы сохранить хорошее настроение.",
            mood_type="positive",
            score_from=70,
            score_to=100,
        ),
        RecommendationModel(
            rec_name="Поблагодарить себя",
            rec_text="Запишите одну вещь, за которую вы можете себя сегодня похвалить.",
            mood_type="positive",
            score_from=65,
            score_to=100,
        ),
        RecommendationModel(
            rec_name="Отдых без телефона",
            rec_text="Отложите телефон на 20 минут и дайте мозгу немного тишины.",
            mood_type="neutral",
            score_from=35,
            score_to=75,
        ),
        RecommendationModel(
            rec_name="Ранний сон",
            rec_text="Если чувствуете усталость, попробуйте лечь спать немного раньше обычного.",
            mood_type="negative",
            score_from=0,
            score_to=45,
        ),
    ]

    existing_names = {item.rec_name for item in db.query(RecommendationModel).all()}

    new_recommendations = [
        rec for rec in recommendations if rec.rec_name not in existing_names
    ]

    if not new_recommendations:
        print("Seed: тестовые рекомендации уже созданы")
        return

    db.add_all(new_recommendations)
    db.commit()

    print(f"Seed: создано рекомендаций: {len(new_recommendations)}")


def seed_notes_for_user(db: Session, user_id: int) -> None:
    existing_notes_count = (
        db.query(NoteModel).filter(NoteModel.user_id == user_id).count()
    )

    if existing_notes_count >= 20:
        print("Seed: тестовые записи пользователя уже есть, пропускаем")
        return

    now = datetime.utcnow()

    notes_data = [
        {
            "days_ago": 0,
            "text": "Сегодня чувствую себя спокойно, есть желание немного почитать и отдохнуть.",
            "translated": "Today I feel calm, I want to read a little and rest.",
            "label": "neutral",
            "score": 62,
        },
        {
            "days_ago": 1,
            "text": "Был продуктивный день, получилось закрыть несколько важных задач.",
            "translated": "It was a productive day, I managed to finish several important tasks.",
            "label": "positive",
            "score": 82,
        },
        {
            "days_ago": 2,
            "text": "Чувствую усталость и немного раздражения, хочется тишины.",
            "translated": "I feel tired and a little irritated, I want some silence.",
            "label": "negative",
            "score": 28,
        },
        {
            "days_ago": 3,
            "text": "Настроение нормальное, без сильных эмоций, день прошёл ровно.",
            "translated": "My mood is normal, without strong emotions, the day went smoothly.",
            "label": "neutral",
            "score": 55,
        },
        {
            "days_ago": 4,
            "text": "Сегодня было тревожно, сложно было сосредоточиться на работе.",
            "translated": "Today I felt anxious, it was hard to focus on work.",
            "label": "negative",
            "score": 22,
        },
        {
            "days_ago": 5,
            "text": "Хорошо провёл время с друзьями, стало намного легче.",
            "translated": "I had a good time with friends and felt much better.",
            "label": "positive",
            "score": 88,
        },
        {
            "days_ago": 6,
            "text": "День был спокойный, удалось немного погулять и переключиться.",
            "translated": "The day was calm, I managed to walk a little and switch my focus.",
            "label": "positive",
            "score": 72,
        },
        {
            "days_ago": 7,
            "text": "Проснулся без сил, весь день хотелось просто лежать.",
            "translated": "I woke up without energy, all day I just wanted to lie down.",
            "label": "negative",
            "score": 18,
        },
        {
            "days_ago": 8,
            "text": "Сегодня чувствую уверенность, есть энергия на спорт и дела.",
            "translated": "Today I feel confident, I have energy for sports and tasks.",
            "label": "positive",
            "score": 90,
        },
        {
            "days_ago": 9,
            "text": "Было немного грустно, но музыка помогла отвлечься.",
            "translated": "I felt a little sad, but music helped me distract myself.",
            "label": "neutral",
            "score": 48,
        },
        {
            "days_ago": 10,
            "text": "Получилось хорошо отдохнуть, настроение стало лучше.",
            "translated": "I managed to rest well, my mood became better.",
            "label": "positive",
            "score": 76,
        },
        {
            "days_ago": 11,
            "text": "Слишком много задач, чувствую перегруз и напряжение.",
            "translated": "Too many tasks, I feel overloaded and tense.",
            "label": "negative",
            "score": 25,
        },
        {
            "days_ago": 12,
            "text": "Обычный день, ничего особенного, настроение стабильное.",
            "translated": "An ordinary day, nothing special, my mood is stable.",
            "label": "neutral",
            "score": 58,
        },
        {
            "days_ago": 13,
            "text": "После прогулки стало лучше, появилось больше спокойствия.",
            "translated": "After the walk I felt better and calmer.",
            "label": "positive",
            "score": 68,
        },
        {
            "days_ago": 14,
            "text": "Сегодня было сложно общаться, хотелось побыть одному.",
            "translated": "Today it was hard to communicate, I wanted to be alone.",
            "label": "negative",
            "score": 35,
        },
        {
            "days_ago": 15,
            "text": "День получился приятный, вечером хочу посмотреть фильм.",
            "translated": "The day turned out pleasant, I want to watch a movie in the evening.",
            "label": "positive",
            "score": 74,
        },
        {
            "days_ago": 16,
            "text": "Есть небольшая тревога, но в целом состояние рабочее.",
            "translated": "There is a little anxiety, but overall I can work.",
            "label": "neutral",
            "score": 52,
        },
        {
            "days_ago": 17,
            "text": "Сильно устал после учебы, нужно нормально поесть и лечь пораньше.",
            "translated": "I got very tired after studying, I need to eat properly and go to bed earlier.",
            "label": "negative",
            "score": 30,
        },
        {
            "days_ago": 18,
            "text": "Сегодня вдохновлён, хочется сделать что-то полезное и важное.",
            "translated": "Today I feel inspired, I want to do something useful and important.",
            "label": "positive",
            "score": 86,
        },
        {
            "days_ago": 19,
            "text": "Настроение среднее, хочется немного порядка и понятного плана.",
            "translated": "My mood is average, I want some order and a clear plan.",
            "label": "neutral",
            "score": 50,
        },
    ]

    existing_texts = {
        item.orig_text
        for item in db.query(NoteModel).filter(NoteModel.user_id == user_id).all()
    }

    notes = []

    for item in notes_data:
        if item["text"] in existing_texts:
            continue

        created_at = now - timedelta(days=item["days_ago"])
        model_confidence = calculate_confidence(item["score"])

        note = NoteModel(
            user_id=user_id,
            orig_text=item["text"],
            translate_text=item["translated"],
            translate_status="done",
            sentiment_label=item["label"],
            sentiment_score=item["score"],
            model_confidence=model_confidence,
            created_at=created_at,
            updated_at=created_at,
        )

        notes.append(note)

    if not notes:
        print("Seed: тестовые записи уже созданы")
        return

    db.add_all(notes)
    db.commit()

    for note in notes:
        db.refresh(note)
        attach_recommendations_for_seed(db, note)

    print(f"Seed: создано тестовых записей: {len(notes)}")


def attach_recommendations_for_seed(db: Session, note: NoteModel) -> None:
    recommendations = (
        db.query(RecommendationModel)
        .filter(
            RecommendationModel.score_from <= note.sentiment_score,
            RecommendationModel.score_to >= note.sentiment_score,
        )
        .limit(2)
        .all()
    )

    note.recommendations = recommendations

    db.commit()

from datetime import date, datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Vocabulary(Base):
    __tablename__ = "vocabulary"
    __table_args__ = (
        UniqueConstraint("normalized_expression", name="uq_vocabulary_normalized_expression"),
        CheckConstraint("correct_option >= 0 AND correct_option <= 3", name="ck_vocabulary_correct_option"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simple_word: Mapped[str] = mapped_column(String(255), nullable=False)
    advanced_word: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_expression: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    translation_uz: Mapped[str] = mapped_column(Text, nullable=False)
    translation_ru: Mapped[str] = mapped_column(Text, nullable=False)
    definition_en: Mapped[str] = mapped_column(Text, nullable=False)
    basic_example_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_en: Mapped[str] = mapped_column(Text, nullable=False)
    example_uz: Mapped[str] = mapped_column(Text, nullable=False)
    example_ru: Mapped[str] = mapped_column(Text, nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(32), nullable=False, default="B2–C1")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="everyday_upgrade")
    ielts_usage: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="Writing Task 2 & Speaking Part 3"
    )
    source_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="Cambridge Dictionary"
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A/B/C/D Quiz fields associated with this vocabulary item
    quiz_question_uz: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_question_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_question_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_a: Mapped[str] = mapped_column(String(255), nullable=False)
    option_b: Mapped[str] = mapped_column(String(255), nullable=False)
    option_c: Mapped[str] = mapped_column(String(255), nullable=False)
    option_d: Mapped[str] = mapped_column(String(255), nullable=False)
    correct_option: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def get_options(self) -> list[str]:
        return [self.option_a, self.option_b, self.option_c, self.option_d]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Learner")
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_quiz_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_quizzes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    settings: Mapped["UserSettings"] = relationship(
        "UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint(
            "language_code IN ('uz', 'ru', 'en')",
            name="ck_user_settings_language_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    language_code: Mapped[str] = mapped_column(String(5), nullable=False, default="uz")
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    broadcast_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="settings")


class DailyLesson(Base):
    __tablename__ = "daily_lessons"
    __table_args__ = (
        UniqueConstraint("lesson_date", name="uq_daily_lessons_lesson_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True
    )
    vocabulary_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["DailyLessonItem"]] = relationship(
        "DailyLessonItem",
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="DailyLessonItem.position",
    )


class DailyLessonItem(Base):
    """
    Join table enforcing at the relational level that each daily vocabulary item
    can NEVER be assigned to more than one daily lesson (UNIQUE vocabulary_id).
    """

    __tablename__ = "daily_lesson_items"
    __table_args__ = (
        UniqueConstraint("vocabulary_id", name="uq_daily_lesson_items_vocabulary_id"),
        UniqueConstraint("lesson_id", "position", name="uq_daily_lesson_items_lesson_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("daily_lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vocabulary.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    lesson: Mapped["DailyLesson"] = relationship("DailyLesson", back_populates="items")
    vocabulary: Mapped["Vocabulary"] = relationship("Vocabulary")


class UserDailyProgress(Base):
    __tablename__ = "user_daily_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_date", name="uq_user_daily_progress_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_memorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earned_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserLearnedWord(Base):
    __tablename__ = "user_learned_words"
    __table_args__ = (
        UniqueConstraint("user_id", "vocabulary_id", name="uq_user_learned_words_user_vocab"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vocabulary.id", ondelete="CASCADE"),
        nullable=False,
    )
    learned_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_correct_in_quiz: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    generation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ==============================================================================
# REFERRAL & REWARDS SYSTEM MODELS (Section 8)
# ==============================================================================


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_referrals_status",
        ),
        CheckConstraint(
            "referrer_user_id <> referred_user_id",
            name="ck_referrals_no_self_referral",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referred_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suspicion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        UniqueConstraint("user_id", "milestone", name="uq_referral_rewards_user_milestone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reward_type: Mapped[str] = mapped_column(String(64), nullable=False)
    milestone: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BonusPack(Base):
    __tablename__ = "bonus_packs"
    __table_args__ = (
        UniqueConstraint("pack_type", name="uq_bonus_packs_pack_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_type: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    required_referrals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    words: Mapped[list["BonusPackWord"]] = relationship(
        "BonusPackWord",
        back_populates="pack",
        cascade="all, delete-orphan",
        order_by="BonusPackWord.position",
    )


class BonusPackWord(Base):
    __tablename__ = "bonus_pack_words"
    __table_args__ = (
        UniqueConstraint("pack_id", "vocabulary_id", name="uq_bonus_pack_words_pack_vocab"),
        UniqueConstraint("pack_id", "position", name="uq_bonus_pack_words_pack_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bonus_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vocabulary.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    pack: Mapped["BonusPack"] = relationship("BonusPack", back_populates="words")
    vocabulary: Mapped["Vocabulary"] = relationship("Vocabulary")


class UserBonusProgress(Base):
    __tablename__ = "user_bonus_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "pack_id", name="uq_user_bonus_progress_user_pack"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pack_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bonus_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_quizzes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ==============================================================================
# MULTI-ADMIN & ADMIN BROADCAST SYSTEM MODELS (Section 16)
# ==============================================================================


class AdminRecord(Base):
    __tablename__ = "admins"
    __table_args__ = (
        UniqueConstraint("telegram_id", name="uq_admins_telegram_id"),
        CheckConstraint(
            "role IN ('super_admin', 'moderator')",
            name="ck_admins_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="moderator"
    )
    added_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Broadcast(Base):
    __tablename__ = "broadcasts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'failed')",
            name="ck_broadcasts_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="text"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        UniqueConstraint(
            "broadcast_id", "user_id", name="uq_broadcast_recipients_broadcast_user"
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name="ck_broadcast_recipients_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("broadcasts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserJourneyProgress(Base):
    __tablename__ = "user_journey_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "node_id", name="uq_user_journey_progress_user_node"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserGameRun(Base):
    __tablename__ = "user_game_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    game_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earned_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

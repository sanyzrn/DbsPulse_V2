"""مجوزهای اداری، نقش پشتیبانی، و ماژول‌های قابل خاموش‌کردن (نیمهٔ دوم P0-03)

Revision ID: a83f61b0d472
Revises: f5c2d90a1e47
Create Date: 2026-08-15

**همهٔ کاربران HR موجود، همهٔ مجوزها را می‌گیرند.** بدون این، این مایگریشن هر
استقرار موجود را می‌شکست: دیروز HR همه‌کاره بود و امروز به هیچ صفحهٔ اداری‌ای
دسترسی ندارد.

پس این مایگریشن *تفکیک وظایف را تحمیل نمی‌کند* — آن را **ممکن** می‌کند. سازمانی
که بخواهد، حساب پشتیبانی می‌سازد و مجوزها را از HR می‌گیرد. سازمان یک‌نفره‌ای که
نخواهد، دقیقاً مثل امروز کار می‌کند. تحمیل‌کردنش در یک مایگریشن یعنی کسی صبح
بیدار شود و نتواند وارد بخشی شود که دیروز مالِ او بود.

ماژول‌ها ردیف اولیه نمی‌گیرند: نبودِ ردیف یعنی «پیش‌فرضِ خودت» (core/modules.py).
با این کار افزودن ماژول تازه در آینده به مایگریشن نیاز ندارد.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a83f61b0d472"
down_revision = "f5c2d90a1e47"
branch_labels = None
depends_on = None

CAPABILITIES = (
    "manage_users",
    "manage_scoring",
    "manage_integrations",
    "manage_modules",
    "view_diagnostics",
)


def upgrade() -> None:
    # نقش تازه به enum موجود اضافه می‌شود. ALTER TYPE ... ADD VALUE در پستگرس
    # داخل بلوک تراکنشی محدودیت دارد، ولی alembic هر مایگریشن را در تراکنش خودش
    # اجرا می‌کند و پستگرس ۱۲ به بعد این را می‌پذیرد.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'support'")

    capability = postgresql.ENUM(*CAPABILITIES, name="capability", create_type=False)
    capability.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("capability", capability, nullable=False),
        sa.Column(
            "granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "capability", name="uq_user_capability"),
    )
    op.create_index("ix_user_capabilities_user", "user_capabilities", ["user_id"])

    op.create_table(
        "module_settings",
        sa.Column("key", sa.String(length=50), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # هر کاربر HR موجود، همهٔ مجوزها. granted_by خالی می‌ماند چون هیچ انسانی
    # این‌ها را نداده — و همین صادق‌ترین ثبت است.
    op.execute(
        sa.text(
            """
            INSERT INTO user_capabilities (user_id, capability)
            SELECT u.id, c.capability::capability
            FROM users u
            CROSS JOIN (SELECT unnest(:caps) AS capability) c
            WHERE u.role = 'hr'
            ON CONFLICT (user_id, capability) DO NOTHING
            """
        ).bindparams(sa.bindparam("caps", value=list(CAPABILITIES), type_=postgresql.ARRAY(sa.Text)))
    )


def downgrade() -> None:
    op.drop_table("module_settings")
    op.drop_index("ix_user_capabilities_user", table_name="user_capabilities")
    op.drop_table("user_capabilities")
    postgresql.ENUM(name="capability").drop(op.get_bind(), checkfirst=True)
    # مقدار enum برداشته نمی‌شود: پستگرس DROP VALUE ندارد، و بازسازی کل نوع
    # یعنی بازنویسی ستون role روی هر ردیف. یک مقدارِ بلااستفاده بی‌ضرر است.

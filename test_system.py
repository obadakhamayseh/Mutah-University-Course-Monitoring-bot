import asyncio
import sys
from datetime import datetime

# Windows stdout encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fetcher.mutah import MutahFetcher, SectionInfo
from db.database import init_db, async_session
from db.crud import (
    get_or_create_user,
    add_subscription,
    get_unique_active_sections,
    get_subscribers_for_section,
    update_section_cache,
    get_section_cache,
    reset_subscription_notification,
)
from worker.monitor import SectionMonitor, format_available_alert


async def run_system_tests():
    print("=" * 60)
    print("🧪 بدء الاختبار الشامل لنظام مراقبة مقاعد جامعة مؤتة")
    print("=" * 60)

    # 1. DB Init
    print("\n[1/5] جاري تهيئة قاعدة البيانات...")
    await init_db()
    print("✅ تم إنشاء وتجهيز الجداول بنجاح.")

    # 2. Live Fetcher Test
    print("\n[2/5] جاري اختبار جلب بيانات حية من بوابة جامعة مؤتة...")
    fetcher = MutahFetcher()
    section = await fetcher.get_section_async("0209100", "1")
    if section:
        print(f"✅ تم الجلب بنجاح:")
        print(f"   - اسم المادة: {section.course_name}")
        print(f"   - الشعبة: {section.section}")
        print(f"   - المدرس: {section.instructor}")
        print(f"   - السعة: {section.capacity} | المسجلين: {section.enrolled} | المتاح: {section.available_seats}")
        print(f"   - حالة الشعبة: {'ممتلئة 🔴' if section.is_full else 'شاغرة 🟢'}")
    else:
        print("❌ فشل جلب بيانات المادة الحية.")
        return False

    # 3. User & Subscription Creation
    print("\n[3/5] جاري اختبار تسجيل مستخدم واشتراك تجريبي...")
    async with async_session() as session:
        user = await get_or_create_user(
            session=session,
            telegram_id=987654321,
            username="student_tester",
            first_name="أحمد",
        )
        sub, created = await add_subscription(
            session=session,
            user_id=user.id,
            course_id=section.course_id,
            section_no=section.section,
            course_name=section.course_name,
        )
        print(f"✅ تم إنشاء المستخدم: {user.first_name} (ID: {user.telegram_id})")
        print(f"✅ تم حفظ الاشتراك: {sub.course_name} شعبة {sub.section_no} (جديد: {created})")

    # 4. Deduplication Verification
    print("\n[4/5] جاري اختبار محرك منع التكرار (Deduplication)...")
    async with async_session() as session:
        # Add another user watching the EXACT same course and section
        user2 = await get_or_create_user(session, 112233445, "student_two", "خالد")
        await add_subscription(session, user2.id, section.course_id, section.section, section.course_name)

        unique_sections = await get_unique_active_sections(session)
        print(f"✅ عدد المستخدمين المتابعين للشعبة: 2")
        print(f"✅ عدد طلبات الفحص المطلوبة لخادم الجامعة: {len(unique_sections)} طلب فقط!")
        assert len(unique_sections) == 1, "Deduplication failed!"
        print(f"   - الشعب المراقبة فريداً: {unique_sections}")

    # 5. Worker Alert Logic & State Transition Simulation
    print("\n[5/5] جاري محاكاة انتقال الحالة من ممتلئة (FULL) إلى شاغرة (AVAILABLE)...")
    alerts_triggered = []

    async def mock_notify(telegram_id: int, msg: str, course_id: str, sec_no: str) -> bool:
        alerts_triggered.append((telegram_id, course_id, sec_no))
        print(f"   📩 تم إرسال إشعار فوري للمستخدم {telegram_id}: توفر مقعد في {course_id} شعبة {sec_no}!")
        return True

    monitor = SectionMonitor(fetcher=fetcher, notify_callback=mock_notify)

    # Simulate section becoming available with 2 seats
    mock_available_section = SectionInfo(
        college="الآداب",
        course_id="0209100",
        course_name="أساسيات اللغة الفرنسية",
        section="1",
        instructor="د.ايمن الصمادي",
        capacity=80,
        enrolled=78,
        available_seats=2,
        is_full=False,
        days="أحد،ثلاثاء،خميس",
        time_from="13.3",
        time_to="14.3",
        room="101",
        notes="",
    )

    # Ensure cache has it as FULL first
    async with async_session() as session:
        await update_section_cache(
            session=session,
            course_id="0209100",
            section_no="1",
            course_name="أساسيات اللغة الفرنسية",
            capacity=80,
            enrolled=80,
            available_seats=0,
            is_full=True,
        )

    # Directly test the transition logic using a mock fetcher
    class MockFetcher:
        async def get_section_async(self, course_id, section_no):
            return mock_available_section

    # Reset notification flags before the test so we simulate a clean transition
    async with async_session() as session:
        await reset_subscription_notification(session, "0209100", "1")

    monitor.fetcher = MockFetcher()
    await monitor.check_single_section("0209100", "1")

    async with async_session() as session:
        subscribers = await get_subscribers_for_section(session, "0209100", "1")
    print(f"✅ عدد المشتركين الفعليين: {len(subscribers)}")
    print(f"✅ عدد الإشعارات المرسلة: {len(alerts_triggered)}")
    assert len(alerts_triggered) == len(subscribers), f"Expected {len(subscribers)} alerts, got {len(alerts_triggered)}"
    print("✅ تم تسليم الإشعار لكافة الطلاب المشتركين بنجاح!")

    # Verify that a second check does NOT re-notify (anti-spam / deduplicated notifications)
    alerts_triggered.clear()
    await monitor.check_single_section("0209100", "1")
    print(f"✅ فحص لاحق بدون تغيير: عدد الإشعارات الجديدة = {len(alerts_triggered)} (تم منع تكرار الإشعار بنجاح!)")
    assert len(alerts_triggered) == 0, "Repeated notification was sent!"

    print("\n" + "=" * 60)
    print("🎉 جميع الاختبارات المعمارية والوظيفية نجحت بنسبة 100%!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    asyncio.run(run_system_tests())

import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  BookOpen,
  Clock,
  Crown,
  ExternalLink,
  FileText,
  HelpCircle,
  Lock,
  MessageCircle,
  Play,
  Plus,
  Search,
  Trash2,
  Unlock,
  UserCheck,
  UserPlus,
  X,
} from 'lucide-react';
import {
  fetchAdminMockTests,
  fetchMockTestMaterials,
  fetchMockTestsCatalog,
  manageAdminMockTestAccess,
  saveAdminMockTest,
} from '../lib/api';
import {
  getTelegramWebApp,
  hapticImpact,
  hapticNotification,
  hapticSelection,
} from '../lib/telegram';
import { useAppStore } from '../store/useAppStore';
import { LanguageCode, MockTestItem } from '../types/miniapp';

interface MockTestsModalProps {
  isAdmin: boolean;
}

type MockSubTab = 'catalog' | 'my_tests' | 'support' | 'admin';

const LABELS: Record<LanguageCode, Record<string, string>> = {
  uz: {
    title: '📝 IELTS MOCK TEST',
    sub: 'Reading • Listening • Writing • Speaking • Full Mock',
    tab_catalog: '📝 Katalog',
    tab_my: '🔓 Mening Testlarim',
    tab_support: '💬 Admin (@n0omg)',
    tab_admin: '👑 Boshqaruv',
    search_ph: 'Mock Test nomi yoki turkum bo‘yicha qidirish...',
    all_cats: 'Barchasi',
    unlocked: '🔓 Ochiq',
    locked: '🔒 Yopiq',
    start_test: '🚀 Testni boshlash',
    open_materials: '📥 Materiallarni ochish',
    contact_admin: '💬 ADMIN BILAN BOG‘LANISH',
    write_admin: '💬 ADMINGA YOZISH',
    support_msg:
      'Mock Test haqida batafsil ma’lumot olish uchun admin bilan bog‘laning: @n0omg',
    no_my_tests: 'Sizda hozircha ochilgan Mock Testlar mavjud emas.',
    duration_min: 'daqiqa',
    questions_cnt: 'savol',
    expires: 'Muddat',
    permanent: 'Doimiy (Permanent)',
  },
  ru: {
    title: '📝 IELTS MOCK TEST',
    sub: 'Reading • Listening • Writing • Speaking • Full Mock',
    tab_catalog: '📝 Каталог',
    tab_my: '🔓 Мои Тесты',
    tab_support: '💬 Админ (@n0omg)',
    tab_admin: '👑 Управление',
    search_ph: 'Поиск по названию или категории Mock Test...',
    all_cats: 'Все',
    unlocked: '🔓 Открыт',
    locked: '🔒 Закрыт',
    start_test: '🚀 Начать тест',
    open_materials: '📥 Открыть материалы',
    contact_admin: '💬 СВЯЗАТЬСЯ С АДМИНОМ',
    write_admin: '💬 НАПИСАТЬ АДМИНУ',
    support_msg:
      'Для получения подробной информации о Mock Test свяжитесь с админом: @n0omg',
    no_my_tests: 'У вас пока нет открытых Mock Test.',
    duration_min: 'мин',
    questions_cnt: 'вопр.',
    expires: 'Срок доступа',
    permanent: 'Постоянный',
  },
  en: {
    title: '📝 IELTS MOCK TEST',
    sub: 'Reading • Listening • Writing • Speaking • Full Mock',
    tab_catalog: '📝 Catalog',
    tab_my: '🔓 My Mock Tests',
    tab_support: '💬 Admin (@n0omg)',
    tab_admin: '👑 Admin Panel',
    search_ph: 'Search Mock Tests by title or category...',
    all_cats: 'All',
    unlocked: '🔓 Unlocked',
    locked: '🔒 Locked',
    start_test: '🚀 Start Test',
    open_materials: '📥 Open Materials',
    contact_admin: '💬 CONTACT ADMIN',
    write_admin: '💬 MESSAGE ADMIN',
    support_msg:
      'For detailed information about Mock Tests, please contact the admin: @n0omg',
    no_my_tests: 'You do not have any unlocked Mock Tests yet.',
    duration_min: 'mins',
    questions_cnt: 'questions',
    expires: 'Access',
    permanent: 'Permanent',
  },
};

export const MockTestsModal: React.FC<MockTestsModalProps> = ({ isAdmin }) => {
  const queryClient = useQueryClient();
  const { lang, closeModal } = useAppStore();
  const L = LABELS[lang] || LABELS.uz;

  const [tab, setTab] = useState<MockSubTab>('catalog');
  const [searchQ, setSearchQ] = useState<string>('');
  const [selectedCat, setSelectedCat] = useState<string>('All');
  const [activeMaterialsTest, setActiveMaterialsTest] =
    useState<MockTestItem | null>(null);
  const [loadingTestId, setLoadingTestId] = useState<number | null>(null);
  const [statusBanner, setStatusBanner] = useState<string>('');

  // Admin state
  const [userSearchQ, setUserSearchQ] = useState<string>('');
  const [grantTestId, setGrantTestId] = useState<number>(1);
  const [grantUserId, setGrantUserId] = useState<string>('');
  const [grantDuration, setGrantDuration] = useState<string>('permanent');
  const [newTitle, setNewTitle] = useState<string>('');
  const [newCat, setNewCat] = useState<string>('Reading');
  const [newDesc, setNewDesc] = useState<string>('');
  const [newPriceUzs, setNewPriceUzs] = useState<string>('45000');
  const [newDuration, setNewDuration] = useState<string>('60');
  const [newQuestions, setNewQuestions] = useState<string>('40');
  const [newMaterialText, setNewMaterialText] = useState<string>('');
  const [newAnswerKeyText, setNewAnswerKeyText] = useState<string>('');
  const [editPriceTestId, setEditPriceTestId] = useState<number | null>(null);
  const [editPriceVal, setEditPriceVal] = useState<string>('');

  const { data: catalogData, isLoading } = useQuery({
    queryKey: ['mock_tests_catalog'],
    queryFn: fetchMockTestsCatalog,
  });

  const { data: adminData, refetch: refetchAdmin } = useQuery({
    queryKey: ['admin_mock_tests', userSearchQ],
    queryFn: () => fetchAdminMockTests(userSearchQ),
    enabled: isAdmin && tab === 'admin',
  });

  const openSupportLink = () => {
    hapticImpact('medium');
    const url = catalogData?.support_url || 'https://t.me/n0omg';
    const tg = getTelegramWebApp();
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  const handleOpenUnlockedTest = async (testId: number) => {
    setLoadingTestId(testId);
    hapticImpact('medium');
    try {
      const res = await fetchMockTestMaterials(testId);
      if (res.ok && res.test) {
        setActiveMaterialsTest(res.test);
        hapticNotification('success');
      }
    } catch {
      hapticNotification('error');
      setTab('support');
    } finally {
      setLoadingTestId(null);
    }
  };

  const handleAdminCreateTest = async () => {
    if (!newTitle.trim()) return;
    hapticImpact('medium');
    const materials = [];
    if (newMaterialText.trim()) {
      materials.push({
        file_type: 'text',
        material_role: 'question_paper',
        title: `${newTitle.trim()} — Question Booklet`,
        text_content: newMaterialText.trim(),
      });
    }
    if (newAnswerKeyText.trim()) {
      materials.push({
        file_type: 'text',
        material_role: 'answer_key',
        title: `${newTitle.trim()} — Official Answer Key`,
        text_content: newAnswerKeyText.trim(),
      });
    }

    await saveAdminMockTest({
      action: 'create',
      title: newTitle.trim(),
      category: newCat,
      description: newDesc.trim() || newTitle.trim(),
      price_uzs: parseInt(newPriceUzs || '0', 10) || 0,
      duration_minutes: parseInt(newDuration || '60', 10) || 60,
      questions_count: parseInt(newQuestions || '40', 10) || 40,
      materials,
    });
    setNewTitle('');
    setNewDesc('');
    setNewMaterialText('');
    setNewAnswerKeyText('');
    setStatusBanner('✅ Yangi Mock Test yaratildi va katalogga chiqarildi!');
    queryClient.invalidateQueries({ queryKey: ['mock_tests_catalog'] });
    refetchAdmin();
  };

  const handleAdminUpdatePrice = async (testId: number) => {
    const val = parseInt(editPriceVal || '0', 10);
    if (Number.isNaN(val) || val < 0) return;
    hapticImpact('light');
    await saveAdminMockTest({
      action: 'update',
      test_id: testId,
      price_uzs: val,
    });
    setEditPriceTestId(null);
    setStatusBanner(`✅ Mock Test #${testId} narxi yangilandi!`);
    queryClient.invalidateQueries({ queryKey: ['mock_tests_catalog'] });
    refetchAdmin();
  };

  const handleAdminDeleteTest = async (testId: number) => {
    hapticImpact('medium');
    await saveAdminMockTest({ action: 'delete', test_id: testId });
    setStatusBanner(`🗑 Mock Test #${testId} o‘chirildi.`);
    queryClient.invalidateQueries({ queryKey: ['mock_tests_catalog'] });
    refetchAdmin();
  };

  const handleAdminGrantAccess = async () => {
    const uid = parseInt(grantUserId.trim(), 10);
    if (!uid || !grantTestId) return;
    hapticImpact('medium');
    const res = await manageAdminMockTestAccess({
      action: 'grant',
      test_id: grantTestId,
      target_user_id: uid,
      duration_code: grantDuration,
    });
    if (res.ok) {
      hapticNotification('success');
      setStatusBanner(
        `🎉 User ${uid} ga "${res.test_title}" (${res.duration_label}) berildi!`
      );
      setGrantUserId('');
      queryClient.invalidateQueries({ queryKey: ['mock_tests_catalog'] });
      refetchAdmin();
    } else {
      setStatusBanner(`⚠️ ${res.reason || 'Xatolik'}`);
    }
  };

  const handleAdminRevokeAccess = async (testId: number, userId: number) => {
    hapticImpact('light');
    await manageAdminMockTestAccess({
      action: 'revoke',
      test_id: testId,
      target_user_id: userId,
    });
    setStatusBanner(`🔒 User ${userId} ruxsati bekor qilindi.`);
    queryClient.invalidateQueries({ queryKey: ['mock_tests_catalog'] });
    refetchAdmin();
  };

  const tests = catalogData?.tests || [];
  const myTests = catalogData?.my_tests || [];
  const categories = [
    'All',
    'Reading',
    'Listening',
    'Writing',
    'Speaking',
    'Full Mock Test',
  ];

  const filteredTests = tests.filter((t) => {
    if (selectedCat !== 'All' && t.category !== selectedCat) return false;
    if (searchQ.trim()) {
      const q = searchQ.toLowerCase();
      return (
        t.title.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.category.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 bg-voxy-bg/98 backdrop-blur-xl flex flex-col overflow-hidden">
      {/* Top Bar */}
      <div className="px-4 pt-3.5 pb-3 border-b border-voxy-border bg-voxy-secondary/90 flex items-center justify-between gap-2 shrink-0">
        <div>
          <h2 className="text-sm sm:text-base font-display font-bold text-voxy-text">
            {L.title}
          </h2>
          <p className="text-[11px] text-voxy-muted">{L.sub}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            hapticImpact('light');
            closeModal();
          }}
          className="p-2 rounded-2xl bg-voxy-card border border-voxy-border text-voxy-muted hover:text-voxy-text"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Tabs */}
      <div className="px-3.5 py-2.5 bg-voxy-bg border-b border-voxy-border flex items-center gap-1.5 overflow-x-auto shrink-0">
        <button
          type="button"
          onClick={() => {
            hapticSelection();
            setActiveMaterialsTest(null);
            setTab('catalog');
          }}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            tab === 'catalog'
              ? 'bg-gradient-to-r from-voxy-purple to-indigo-600 text-white shadow'
              : 'bg-voxy-card border border-voxy-border text-voxy-muted'
          }`}
        >
          {L.tab_catalog} ({tests.length})
        </button>
        <button
          type="button"
          onClick={() => {
            hapticSelection();
            setActiveMaterialsTest(null);
            setTab('my_tests');
          }}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            tab === 'my_tests'
              ? 'bg-gradient-to-r from-voxy-green to-emerald-600 text-slate-950 shadow'
              : 'bg-voxy-card border border-voxy-border text-voxy-muted'
          }`}
        >
          {L.tab_my} ({myTests.length})
        </button>
        <button
          type="button"
          onClick={() => {
            hapticSelection();
            setActiveMaterialsTest(null);
            setTab('support');
          }}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            tab === 'support'
              ? 'bg-voxy-blue text-slate-950 shadow'
              : 'bg-voxy-card border border-voxy-border text-voxy-muted'
          }`}
        >
          {L.tab_support}
        </button>
        {isAdmin && (
          <button
            type="button"
            onClick={() => {
              hapticSelection();
              setActiveMaterialsTest(null);
              setTab('admin');
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
              tab === 'admin'
                ? 'bg-voxy-gold text-slate-950 shadow'
                : 'bg-voxy-card border border-voxy-border text-voxy-gold'
            }`}
          >
            {L.tab_admin}
          </button>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto px-3.5 py-3.5 max-w-md w-full mx-auto space-y-3.5 pb-12">
        {isLoading && (
          <div className="py-16 text-center text-xs text-voxy-muted">
            Loading IELTS Mock Tests...
          </div>
        )}

        {/* Active Protected Materials Viewer */}
        {activeMaterialsTest && (
          <div className="bg-voxy-card border border-voxy-green/50 rounded-3xl p-4 space-y-3.5 shadow-greenGlow">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="px-2 py-0.5 rounded-lg bg-voxy-green/20 text-voxy-green text-[10px] font-extrabold">
                  {activeMaterialsTest.category} • UNLOCKED
                </span>
                <h3 className="text-base font-display font-bold text-voxy-text mt-1">
                  {activeMaterialsTest.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveMaterialsTest(null)}
                className="text-xs font-bold text-voxy-blue underline"
              >
                ← Back
              </button>
            </div>

            {activeMaterialsTest.instructions && (
              <div className="bg-voxy-secondary border border-voxy-border rounded-2xl p-3 text-xs text-voxy-text">
                📋 {activeMaterialsTest.instructions}
              </div>
            )}

            <div className="space-y-2.5">
              {(activeMaterialsTest.files || []).map((f) => (
                <div
                  key={f.id}
                  className="bg-voxy-secondary/90 border border-voxy-border rounded-2xl p-3.5 space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] font-bold text-voxy-blue">
                    <span>
                      📎 [{f.material_role.replace('_', ' ').toUpperCase()}]{' '}
                      {f.title}
                    </span>
                    <span className="uppercase text-voxy-gold">
                      {f.file_type}
                    </span>
                  </div>
                  {f.text_content && (
                    <pre className="whitespace-pre-wrap font-sans text-xs text-voxy-text leading-relaxed pt-1">
                      {f.text_content}
                    </pre>
                  )}
                  {f.telegram_file_id && !f.text_content && (
                    <div className="text-[11px] text-voxy-muted">
                      Telegram File attached ({f.file_name || f.file_type}) —
                      available in Telegram Bot chat via 🔓 MENING TESTLARIM.
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 1: PUBLIC CATALOG */}
        {!activeMaterialsTest && tab === 'catalog' && (
          <div className="space-y-3">
            {/* Search Bar */}
            <div className="relative">
              <Search className="w-4 h-4 text-voxy-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder={L.search_ph}
                className="w-full pl-9 pr-4 py-2.5 rounded-2xl bg-voxy-card border border-voxy-border text-xs text-voxy-text placeholder:text-voxy-muted focus:outline-none focus:border-voxy-purple"
              />
            </div>

            {/* Category Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => {
                    hapticSelection();
                    setSelectedCat(cat);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-[11px] font-bold whitespace-nowrap border ${
                    selectedCat === cat
                      ? 'bg-voxy-purple/25 border-voxy-purple text-voxy-blue'
                      : 'bg-voxy-card border-voxy-border text-voxy-muted'
                  }`}
                >
                  {cat === 'All' ? L.all_cats : cat}
                </button>
              ))}
            </div>

            {/* Mock Test Cards */}
            <div className="space-y-3">
              {filteredTests.map((t) => (
                <motion.div
                  key={t.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-3 shadow-glass"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="px-2 py-0.5 rounded-lg bg-voxy-purple/20 text-voxy-blue text-[10px] font-extrabold">
                          {t.category}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold flex items-center gap-1 ${
                            t.is_unlocked
                              ? 'bg-voxy-green/20 text-voxy-green'
                              : 'bg-amber-500/20 text-amber-300'
                          }`}
                        >
                          {t.is_unlocked ? (
                            <Unlock className="w-3 h-3" />
                          ) : (
                            <Lock className="w-3 h-3" />
                          )}
                          {t.is_unlocked ? L.unlocked : L.locked}
                        </span>
                      </div>
                      <h3 className="text-sm sm:text-base font-display font-bold text-voxy-text">
                        {t.title}
                      </h3>
                    </div>

                    <div className="bg-voxy-secondary border border-voxy-gold/40 rounded-2xl px-2.5 py-1.5 text-right shrink-0">
                      <div className="text-xs font-extrabold text-voxy-gold">
                        {t.price_formatted}
                      </div>
                    </div>
                  </div>

                  <p className="text-xs text-voxy-muted leading-relaxed">
                    {t.description}
                  </p>

                  <div className="flex items-center gap-3 text-[11px] text-voxy-muted font-semibold">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-voxy-blue" />
                      {t.duration_minutes} {L.duration_min}
                    </span>
                    <span className="flex items-center gap-1">
                      <HelpCircle className="w-3.5 h-3.5 text-voxy-purple" />
                      {t.questions_count} {L.questions_cnt}
                    </span>
                    <span className="flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5 text-voxy-green" />
                      {t.materials_count || 2} files
                    </span>
                  </div>

                  {t.is_unlocked ? (
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <button
                        type="button"
                        disabled={loadingTestId === t.id}
                        onClick={() => handleOpenUnlockedTest(t.id)}
                        className="py-2.5 px-3 rounded-2xl bg-voxy-green text-slate-950 font-extrabold text-xs flex items-center justify-center gap-1.5 shadow"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        {L.start_test}
                      </button>
                      <button
                        type="button"
                        disabled={loadingTestId === t.id}
                        onClick={() => handleOpenUnlockedTest(t.id)}
                        className="py-2.5 px-3 rounded-2xl bg-voxy-secondary border border-voxy-border text-voxy-text font-bold text-xs flex items-center justify-center gap-1.5"
                      >
                        <BookOpen className="w-3.5 h-3.5 text-voxy-blue" />
                        {L.open_materials}
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setTab('support')}
                      className="w-full py-2.5 px-3 rounded-2xl bg-gradient-to-r from-voxy-purple to-indigo-600 text-white font-extrabold text-xs flex items-center justify-center gap-1.5 shadow"
                    >
                      <MessageCircle className="w-3.5 h-3.5" />
                      {L.contact_admin}
                    </button>
                  )}
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: MY MOCK TESTS */}
        {!activeMaterialsTest && tab === 'my_tests' && (
          <div className="space-y-3">
            {myTests.length === 0 ? (
              <div className="bg-voxy-card border border-voxy-border rounded-3xl p-6 text-center space-y-3">
                <Lock className="w-8 h-8 text-voxy-muted mx-auto" />
                <p className="text-xs font-bold text-voxy-text">
                  {L.no_my_tests}
                </p>
                <p className="text-xs text-voxy-muted">{L.support_msg}</p>
                <button
                  type="button"
                  onClick={openSupportLink}
                  className="px-4 py-2.5 rounded-2xl bg-voxy-blue text-slate-950 font-extrabold text-xs inline-flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {L.write_admin}
                </button>
              </div>
            ) : (
              myTests.map((t) => (
                <div
                  key={t.id}
                  className="bg-voxy-card border border-voxy-green/40 rounded-3xl p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="px-2 py-0.5 rounded-lg bg-voxy-green/20 text-voxy-green text-[10px] font-extrabold">
                        {t.category} • {L.unlocked}
                      </span>
                      <h3 className="text-sm font-display font-bold text-voxy-text mt-1">
                        {t.title}
                      </h3>
                    </div>
                    <span className="text-[10px] font-bold text-voxy-gold">
                      {L.expires}:{' '}
                      {t.access_expires_at
                        ? t.access_expires_at.slice(0, 10)
                        : L.permanent}
                    </span>
                  </div>
                  <p className="text-xs text-voxy-muted">{t.description}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => handleOpenUnlockedTest(t.id)}
                      className="py-2.5 rounded-2xl bg-voxy-green text-slate-950 font-extrabold text-xs flex items-center justify-center gap-1.5"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      {L.start_test}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenUnlockedTest(t.id)}
                      className="py-2.5 rounded-2xl bg-voxy-secondary border border-voxy-border text-voxy-text font-bold text-xs flex items-center justify-center gap-1.5"
                    >
                      <BookOpen className="w-3.5 h-3.5 text-voxy-blue" />
                      {L.open_materials}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 3: ADMIN CONTACT (@n0omg) */}
        {!activeMaterialsTest && tab === 'support' && (
          <div className="bg-voxy-card border border-voxy-blue/40 rounded-3xl p-5 text-center space-y-4 shadow-blueGlow">
            <div className="w-12 h-12 rounded-2xl bg-voxy-blue/20 text-voxy-blue flex items-center justify-center mx-auto">
              <MessageCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-display font-bold text-voxy-text">
              {L.contact_admin}
            </h3>
            <p className="text-xs text-voxy-text leading-relaxed">
              {L.support_msg}
            </p>
            <button
              type="button"
              onClick={openSupportLink}
              className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-voxy-blue to-indigo-600 text-white font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg"
            >
              <ExternalLink className="w-4 h-4" />
              {L.write_admin} (@n0omg)
            </button>
          </div>
        )}

        {/* TAB 4: PROTECTED ADMIN MOCK TEST DASHBOARD */}
        {!activeMaterialsTest && isAdmin && tab === 'admin' && (
          <div className="space-y-4">
            {statusBanner && (
              <div className="bg-voxy-green/15 border border-voxy-green/40 rounded-2xl p-3 text-xs font-bold text-voxy-green">
                {statusBanner}
              </div>
            )}

            {/* 1. Grant Complimentary User Access */}
            <div className="bg-voxy-card border border-voxy-gold/40 rounded-3xl p-4 space-y-3">
              <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-1.5">
                <UserPlus className="w-4 h-4 text-voxy-gold" />
                👤 Foydalanuvchiga Mock Test berish
              </h3>

              <select
                value={grantTestId}
                onChange={(e) => setGrantTestId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
              >
                {(adminData?.tests || tests).map((t) => (
                  <option key={t.id} value={t.id}>
                    #{t.id} {t.title} ({t.price_formatted})
                  </option>
                ))}
              </select>

              <div className="space-y-1.5">
                <input
                  type="text"
                  value={userSearchQ}
                  onChange={(e) => setUserSearchQ(e.target.value)}
                  placeholder="🔍 Foydalanuvchi qidirish (ID, @username yoki ism)..."
                  className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                />
                {adminData?.users && adminData.users.length > 0 && (
                  <div className="max-h-28 overflow-y-auto space-y-1 pt-1">
                    {adminData.users.slice(0, 6).map((u) => (
                      <button
                        key={u.user_id}
                        type="button"
                        onClick={() => setGrantUserId(String(u.user_id))}
                        className={`w-full px-2.5 py-1.5 rounded-lg text-left text-[11px] flex items-center justify-between ${
                          grantUserId === String(u.user_id)
                            ? 'bg-voxy-purple text-white'
                            : 'bg-voxy-secondary/70 text-voxy-muted'
                        }`}
                      >
                        <span className="truncate">
                          👤 {u.full_name}{' '}
                          {u.username ? `(@${u.username})` : ''}
                        </span>
                        <span className="font-mono">{u.user_id}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={grantUserId}
                  onChange={(e) => setGrantUserId(e.target.value)}
                  placeholder="Telegram ID (e.g. 123456789)"
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                />
                <select
                  value={grantDuration}
                  onChange={(e) => setGrantDuration(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                >
                  <option value="permanent">♾ Doimiy (Permanent)</option>
                  <option value="24h">⏱ 24 soat (24h)</option>
                  <option value="7d">📅 7 kun (7d)</option>
                  <option value="30d">📆 30 kun (30d)</option>
                </select>
              </div>

              <button
                type="button"
                onClick={handleAdminGrantAccess}
                className="w-full py-2.5 rounded-2xl bg-voxy-gold text-slate-950 font-extrabold text-xs"
              >
                ✅ Ruxsat berish (Grant Access)
              </button>
            </div>

            {/* 2. Active Access Holders & Revoke */}
            {adminData?.holders && adminData.holders.length > 0 && (
              <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-2.5">
                <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-1.5">
                  <UserCheck className="w-4 h-4 text-voxy-green" />
                  👥 Testga ega foydalanuvchilar ({adminData.holders.length})
                </h3>
                <div className="space-y-1.5">
                  {adminData.holders.map((h) => (
                    <div
                      key={`${h.mock_test_id}-${h.user_id}`}
                      className="bg-voxy-secondary rounded-2xl p-2.5 flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="min-w-0">
                        <div className="font-bold text-voxy-text truncate">
                          {h.full_name} ({h.user_id})
                        </div>
                        <div className="text-[10px] text-voxy-muted truncate">
                          {h.test_title} • {h.duration_label}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          handleAdminRevokeAccess(h.mock_test_id, h.user_id)
                        }
                        className="px-2.5 py-1 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-300 text-[10px] font-bold shrink-0"
                      >
                        🔒 Bekor qilish
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 3. Add New Mock Test */}
            <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-2.5">
              <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-1.5">
                <Plus className="w-4 h-4 text-voxy-purple" />
                ➕ Yangi Mock Test qo‘shish
              </h3>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Mock Test nomi..."
                className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
              />
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                >
                  {categories.slice(1).map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  value={newPriceUzs}
                  onChange={(e) => setNewPriceUzs(e.target.value)}
                  placeholder="Narxi (UZS)"
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  value={newDuration}
                  onChange={(e) => setNewDuration(e.target.value)}
                  placeholder="Vaqt (daqiqa)"
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                />
                <input
                  type="number"
                  value={newQuestions}
                  onChange={(e) => setNewQuestions(e.target.value)}
                  placeholder="Savollar soni"
                  className="px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
                />
              </div>
              <textarea
                rows={2}
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Tavsif (Description)..."
                className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
              />
              <textarea
                rows={2}
                value={newMaterialText}
                onChange={(e) => setNewMaterialText(e.target.value)}
                placeholder="Savollar / Reading Passage matni (ixtiyoriy, PDF/Audioni bot orqali ham yuklash mumkin)..."
                className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
              />
              <textarea
                rows={2}
                value={newAnswerKeyText}
                onChange={(e) => setNewAnswerKeyText(e.target.value)}
                placeholder="Answer Key / Javoblar kaliti..."
                className="w-full px-3 py-2 rounded-xl bg-voxy-secondary border border-voxy-border text-xs text-voxy-text"
              />
              <button
                type="button"
                onClick={handleAdminCreateTest}
                className="w-full py-2.5 rounded-2xl bg-voxy-purple text-white font-extrabold text-xs"
              >
                ➕ Nashr qilish (Publish Mock Test)
              </button>
            </div>

            {/* 4. Manage Existing Mock Tests & UZS Prices */}
            <div className="bg-voxy-card border border-voxy-border rounded-3xl p-4 space-y-2.5">
              <h3 className="text-xs sm:text-sm font-display font-bold text-voxy-text flex items-center gap-1.5">
                <Crown className="w-4 h-4 text-voxy-gold" />
                📚 Barcha Mock Testlar ({(adminData?.tests || tests).length})
              </h3>
              <div className="space-y-2">
                {(adminData?.tests || tests).map((t) => (
                  <div
                    key={t.id}
                    className="bg-voxy-secondary rounded-2xl p-3 space-y-2 text-xs"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-bold text-voxy-text">
                          #{t.id} {t.title}
                        </div>
                        <div className="text-[10px] text-voxy-muted">
                          {t.category} • {t.price_formatted} •{' '}
                          {t.active_users_count || 0} users
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleAdminDeleteTest(t.id)}
                        className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    {editPriceTestId === t.id ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="number"
                          value={editPriceVal}
                          onChange={(e) => setEditPriceVal(e.target.value)}
                          placeholder="Yangi narx (UZS)"
                          className="flex-1 px-2.5 py-1.5 rounded-lg bg-voxy-bg border border-voxy-border text-xs"
                        />
                        <button
                          type="button"
                          onClick={() => handleAdminUpdatePrice(t.id)}
                          className="px-3 py-1.5 rounded-lg bg-voxy-green text-slate-950 font-bold text-[11px]"
                        >
                          Saqlash
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setEditPriceTestId(t.id);
                          setEditPriceVal(String(t.price_uzs));
                        }}
                        className="px-2.5 py-1 rounded-lg bg-voxy-bg border border-voxy-border text-[11px] font-bold text-voxy-gold"
                      >
                        💰 Narxni o‘zgartirish (UZS)
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

import { useRef, useState, type FormEvent } from 'react';
import { api, ApiClient } from '../api/client';
import { Icon } from '../components/Icon';
import { usePreferences } from './preferences';

const asset = (file: string) => `${import.meta.env.BASE_URL}assets/${file}`;
export function LandingPage({ onStart }: { onStart: () => void }) {
  const { t } = usePreferences();
  const places = [
    {
      image: 'tokyo.jpg',
      title: 'Tokyo, Fuji & Hakone',
      vi: 'Thành phố, núi và một nhịp đi thư thả.',
      en: 'City streets, mountain views and a gentler pace.',
      altVi: 'Phố gần đền Sensō-ji tại Tokyo',
      altEn: 'A street near Sensō-ji temple in Tokyo',
    },
    {
      image: 'kyoto.jpg',
      title: 'Osaka, Kyoto & Nara',
      vi: 'Văn hóa, phố cổ và những ngôi đền.',
      en: 'Culture, old streets and quiet temples.',
      altVi: 'Cổng torii đỏ tại Kyoto',
      altEn: 'Red torii gates in Kyoto',
    },
    {
      image: 'fuji.jpg',
      title: 'Tokyo, Fuji & Yokohama',
      vi: 'Góc nhìn khác giữa đô thị và cảnh núi.',
      en: 'A different perspective on cities and mountains.',
      altVi: 'Núi Phú Sĩ và chùa Chureito',
      altEn: 'Mount Fuji and Chureito pagoda',
    },
  ];
  return (
    <section className="page landing-page" aria-labelledby="landing-heading">
      <div className="landing-hero">
        <div className="landing-hero-copy">
          <span className="eyebrow landing-kicker">
            {t('HỖ TRỢ LỰA CHỌN TOUR', 'HELP WITH CHOOSING A TOUR')}
          </span>
          <h1 id="landing-heading">
            {t('Chọn kỹ,', 'Choose carefully,')}
            <br />
            {t('đi thảnh thơi.', 'travel with ease.')}
          </h1>
          <p>
            {t(
              'Đối chiếu tour theo nhu cầu, hiểu từng đánh đổi và kiểm chứng dữ kiện trước khi quyết định.',
              'Compare tours against your needs, understand the trade-offs and check the facts before deciding.',
            )}
          </p>
          <div className="landing-hero-actions">
            <button className="btn btn-primary" onClick={onStart}>
              {t('Tìm tour', 'Find tours')}
              <Icon name="arrow" />
            </button>
            <a className="text-action" href="#how-it-works">
              {t('Cách sử dụng', 'How it works')}
              <span aria-hidden="true">↘</span>
            </a>
          </div>
        </div>
        <figure className="landing-hero-landscape">
          <div className="landing-landscape-frame">
            <img
              src={asset('fuji.jpg')}
              alt={t(
                'Núi Phú Sĩ và chùa Chureito tại Nhật Bản',
                'Mount Fuji and Chureito pagoda in Japan',
              )}
              width="1000"
              height="667"
              fetchPriority="high"
            />
          </div>
          <figcaption>
            <span>
              {t('Nhật Bản, một ý tưởng cho chuyến tới.', 'Japan, an idea for your next trip.')}
            </span>
            <span>{t('Ảnh điểm đến', 'Destination photograph')}</span>
          </figcaption>
        </figure>
      </div>
      <section className="landing-local" aria-labelledby="before-trip">
        <div className="landing-local-heading">
          <Icon name="route" />
          <h2 id="before-trip">{t('Trước khi lên đường', 'Before you set off')}</h2>
        </div>
        <div className="landing-local-item">
          <span className="meta-label">{t('Nơi khởi hành', 'Departure city')}</span>
          <p>{t('Bắt đầu từ nơi thuận tiện với bạn.', 'Start from a city that works for you.')}</p>
          <button className="text-action" onClick={onStart}>
            {t('Chọn khi tìm tour', 'Choose when searching')}
            <Icon name="arrow" size={14} />
          </button>
        </div>
        <div className="landing-local-item">
          <span className="meta-label">{t('Chuẩn bị chuyến đi', 'Prepare for your trip')}</span>
          <p>
            {t(
              'Kiểm tra lịch, dịch vụ và điều kiện đi kèm.',
              'Check dates, included services and conditions.',
            )}
          </p>
          <small>
            {t(
              'Lịch khởi hành không đồng nghĩa còn chỗ.',
              'A published departure date does not confirm availability.',
            )}
          </small>
        </div>
      </section>
      <section className="landing-inspiration" aria-labelledby="inspiration-heading">
        <header className="landing-section-heading">
          <h2 id="inspiration-heading">{t('Một nơi để bắt đầu.', 'Somewhere to begin.')}</h2>
          <p>
            {t(
              'Vài góc nhìn về Nhật Bản. Nhu cầu của bạn sẽ là điểm xuất phát khi tìm và so sánh tour.',
              'A few views of Japan. Your needs will be the starting point when searching for and comparing tours.',
            )}
          </p>
        </header>
        <div className="landing-destination-grid">
          {places.map((place, index) => (
            <article
              className={`landing-destination ${index === 0 ? 'landing-destination-wide' : ''}`}
              key={place.title}
            >
              <div className="landing-destination-image">
                <img
                  src={asset(place.image)}
                  alt={t(place.altVi, place.altEn)}
                  width="1000"
                  height="667"
                  loading="lazy"
                />
              </div>
              <span className="landing-place">{t('NHẬT BẢN', 'JAPAN')}</span>
              <h3>{place.title}</h3>
              <p>{t(place.vi, place.en)}</p>
            </article>
          ))}
        </div>
        <div className="landing-inspiration-foot">
          <p>
            {t(
              'Ảnh giới thiệu điểm đến. Tour, giá và điều kiện được cung cấp trong kết quả tìm kiếm.',
              'These photographs introduce destinations. Tours, prices and conditions are provided in search results.',
            )}
          </p>
          <button className="btn" onClick={onStart}>
            {t('Tạo chuyến đi của bạn', 'Start your trip')}
            <Icon name="arrow" />
          </button>
        </div>
      </section>
      <section className="landing-guide" id="how-it-works" aria-labelledby="guide-heading">
        <header className="landing-section-heading">
          <h2 id="guide-heading">
            {t('Hiểu lựa chọn trước khi chọn.', 'Understand your options before choosing.')}
          </h2>
          <p>
            {t(
              'Đi cùng giúp bạn đối chiếu tour trọn gói theo cùng tiêu chí và nhìn rõ thông tin còn thiếu.',
              'Đi cùng compares package tours using the same criteria and makes missing information visible.',
            )}
          </p>
        </header>
        <div className="landing-guide-layout">
          <ol className="guide-steps">
            <li>
              <span>1</span>
              <div>
                <h3>{t('Kể điều bạn cần', 'Tell us what you need')}</h3>
                <p>
                  {t(
                    'Điền thông tin chuyến đi, thêm URL tour hoặc ghi chú riêng nếu có.',
                    'Enter your trip details and add a tour URL or personal notes if you have them.',
                  )}
                </p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <h3>{t('Xác nhận và theo dõi', 'Confirm and follow progress')}</h3>
                <p>
                  {t(
                    'Kiểm tra nhu cầu, rồi xem hệ thống đang thu thập và đối chiếu điều gì.',
                    'Review your needs, then follow what the system is collecting and comparing.',
                  )}
                </p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <h3>{t('So sánh, hỏi thêm', 'Compare and ask more')}</h3>
                <p>
                  {t(
                    'Mở nguồn từng dữ kiện, đọc phân tích AI và trao đổi để điều chỉnh nhu cầu.',
                    'Open the source for each fact, read the AI analysis and discuss changes to your needs.',
                  )}
                </p>
              </div>
            </li>
          </ol>
          <aside className="guide-preview">
            <div className="guide-preview-heading">
              <Icon name="route" />
              <h3>{t('Một chuyến đi. Nhiều góc nhìn.', 'One trip. Many perspectives.')}</h3>
            </div>
            <p className="guide-preview-quote">
              {t(
                'Giá, lịch trình và điều kiện — cùng đặt cạnh nhau.',
                'Price, itinerary and conditions — side by side.',
              )}
            </p>
            <p>
              {t(
                'Mỗi kết quả giữ đúng yêu cầu đã dùng. Những thay đổi luôn được bạn xác nhận trước khi tìm lại.',
                'Each result keeps the requirements used to produce it. You confirm changes before searching again.',
              )}
            </p>
            <button className="text-action" onClick={onStart}>
              {t('Bắt đầu tìm tour', 'Start finding tours')}
              <Icon name="arrow" />
            </button>
          </aside>
        </div>
      </section>
    </section>
  );
}

export function SupportPage({ onStart }: { onStart: () => void }) {
  const { t } = usePreferences();
  const articles = [
    [
      t('Sửa nhu cầu rồi xác nhận', 'Edit your needs, then confirm'),
      t(
        'Chọn Sửa nhiều mục, sửa từng giá trị hoặc kéo thanh sở thích. Mọi thay đổi được gom chung để xác nhận một lần. Hủy tất cả khôi phục bản đã xác nhận gần nhất.',
        'Choose Edit multiple fields, change individual values or adjust the preference sliders. Changes are grouped for a single confirmation. Cancel all restores the latest confirmed requirements.',
      ),
    ],
    [
      t('Tìm kiếm khi bạn sẵn sàng', 'Search when you are ready'),
      t(
        'Sau khi xác nhận, bấm Tìm kiếm hoặc yêu cầu tìm qua chat. Kết quả cũ còn xem được trong lúc xử lý và được ghi rõ nếu chưa theo nhu cầu mới.',
        'After confirming, select Search or request a search in chat. Previous results remain available while processing, with a clear notice when they use earlier requirements.',
      ),
    ],
    [
      t('Đối chiếu dữ kiện và phân tích', 'Compare facts and analysis'),
      t(
        'Tab Dữ kiện so sánh đặt các tour cạnh nhau. Tab Phân tích AI giải thích đánh đổi và điều còn thiếu, kèm căn cứ để bạn kiểm tra.',
        'The Comparison facts tab places tours side by side. AI analysis explains trade-offs and missing information, with supporting facts for you to check.',
      ),
    ],
    [
      t('Kiểm tra nguồn trước khi quyết định', 'Check the sources before deciding'),
      t(
        'Mở từng ô giá, lịch hoặc chính sách để xem dữ kiện và giới hạn. Giá công bố chưa phải tổng cuối; lịch khởi hành chưa chứng minh còn chỗ.',
        'Open each price, date or policy cell to see its facts and limitations. A published price may not be the final total, and a departure date does not confirm availability.',
      ),
    ],
  ];
  return (
    <section className="page service-page" aria-labelledby="support-heading">
      <div className="service-heading">
        <span className="eyebrow">{t('HỖ TRỢ NGƯỜI DÙNG', 'USER SUPPORT')}</span>
        <h1 id="support-heading">
          {t('Đọc rõ hơn.', 'See more clearly.')}
          <br />
          <em>{t('Chọn tự tin hơn.', 'Choose with confidence.')}</em>
        </h1>
        <p>
          {t(
            'Từ việc sửa nhu cầu đến kiểm tra nguồn: những thao tác bạn cần khi cân nhắc một chuyến đi.',
            'From changing your needs to checking sources: the tools you need when considering a trip.',
          )}
        </p>
      </div>
      <div className="service-layout">
        <div className="support-articles">
          {articles.map(([title, text], index) => (
            <article key={index}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <div>
                <h2>{title}</h2>
                <p>{text}</p>
              </div>
            </article>
          ))}
        </div>
        <aside className="service-note">
          <Icon name="route" size={28} />
          <h2>{t('Tiếp tục chuyến đi của bạn.', 'Continue your journey.')}</h2>
          <p>
            {t(
              'Lượt tìm tour và phần trao đổi đều nằm trong mục Tìm tour.',
              'Your tour searches and conversations are all in Find tours.',
            )}
          </p>
          <button className="btn btn-primary" onClick={onStart}>
            {t('Về Tìm tour', 'Go to Find tours')}
            <Icon name="arrow" />
          </button>
        </aside>
      </div>
    </section>
  );
}

export function ContactPage() {
  const { t } = usePreferences();
  const [category, setCategory] = useState<'feedback' | 'data_issue' | 'support'>('feedback');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ticket, setTicket] = useState('');
  const session = useRef<{ token: string; id: string } | null>(null);
  const sessionKey = useRef(crypto.randomUUID());
  const submission = useRef<{ fingerprint: string; id: string } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError('');
    setTicket('');
    if (!message.trim()) {
      setError(t('Nhập nội dung liên hệ.', 'Enter your message.'));
      return;
    }
    const fingerprint = JSON.stringify({
      category,
      message: message.trim(),
      reply_to: email.trim() || null,
    });
    if (submission.current?.fingerprint !== fingerprint)
      submission.current = { fingerprint, id: crypto.randomUUID() };
    const id = submission.current.id;
    setBusy(true);
    try {
      if (!session.current) {
        const created = await api.session({ idempotencyKey: sessionKey.current });
        session.current = { token: created.token, id: created.session_id ?? created.id };
      }
      const result = await new ApiClient(session.current.token).contact(
        {
          category,
          message: message.trim(),
          reply_to: email.trim() || null,
          client_submission_id: id,
          context: { session_id: session.current.id },
        },
        { idempotencyKey: id },
      );
      setTicket(result.ticket_id);
      setMessage('');
      submission.current = null;
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : t(
              'Chưa gửi được liên hệ. Bạn có thể thử lại.',
              'Your message could not be sent. You can try again.',
            ),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="page service-page" aria-labelledby="contact-heading">
      <div className="service-heading">
        <span className="eyebrow">{t('LIÊN HỆ CHÚNG TÔI', 'CONTACT US')}</span>
        <h1 id="contact-heading">
          {t('Một góp ý của bạn,', 'Your feedback,')}
          <br />
          <em>{t('một trải nghiệm tốt hơn.', 'a better experience.')}</em>
        </h1>
        <p>
          {t(
            'Góp ý về cách tìm tour, bảng so sánh hoặc những thông tin bạn muốn nhìn rõ hơn.',
            'Share feedback on finding tours, the comparison table or information you would like to see more clearly.',
          )}
        </p>
      </div>
      <div className="service-layout">
        <form className="contact-form form-card" onSubmit={submit}>
          <div className="form-grid">
            <label className="field">
              {t('Loại liên hệ', 'Category')}
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value as typeof category)}
                disabled={busy}
              >
                <option value="feedback">{t('Góp ý trải nghiệm', 'Experience feedback')}</option>
                <option value="data_issue">
                  {t('Thông tin tour / nguồn', 'Tour or source information')}
                </option>
                <option value="support">{t('Cần hỗ trợ', 'Support request')}</option>
              </select>
            </label>
            <label className="field">
              {t('Email liên hệ (tùy chọn)', 'Email address (optional)')}
              <input
                type="email"
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                disabled={busy}
              />
            </label>
          </div>
          <label className="field">
            {t('Bạn muốn nhắn điều gì?', 'What would you like to tell us?')}
            <textarea
              rows={6}
              maxLength={4000}
              required
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder={t(
                'Điều bạn thấy hữu ích, hoặc muốn nhóm cải thiện…',
                'What you found useful, or what we could improve…',
              )}
              disabled={busy}
            />
          </label>
          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}
          {ticket && (
            <p className="notice notice-success" role="status">
              {t('Đã gửi liên hệ. Mã tiếp nhận:', 'Your message has been sent. Reference:')}{' '}
              <strong>{ticket}</strong>
            </p>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? t('Đang gửi…', 'Sending…') : t('Gửi liên hệ', 'Send message')}
            <Icon name="mail" />
          </button>
          <p className="form-hint">
            {t(
              'Để lại email nếu bạn muốn nhận phản hồi. Chỉ gửi thông tin cần thiết cho yêu cầu hỗ trợ.',
              'Leave an email address if you would like a reply. Share only the information needed for your support request.',
            )}
          </p>
        </form>
        <aside className="service-note">
          <Icon name="leaf" size={28} />
          <h2>{t('Đang xây dựng cùng bạn.', 'Building with you.')}</h2>
          <p>
            {t(
              'Đi cùng tập trung vào tour có nguồn, so sánh rõ ràng và những đánh đổi có thể kiểm chứng.',
              'Đi cùng focuses on tours with sources, clear comparisons and verifiable trade-offs.',
            )}
          </p>
          <p>
            {t(
              'Nếu một dữ kiện chưa rõ, hãy gửi tên tour và đường dẫn nguồn để nhóm kiểm tra.',
              'If a fact is unclear, include the tour name and source link so the team can check it.',
            )}
          </p>
        </aside>
      </div>
    </section>
  );
}

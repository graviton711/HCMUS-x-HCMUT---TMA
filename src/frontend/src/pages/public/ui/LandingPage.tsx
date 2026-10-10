import { Icon } from '../../../shared/ui';
import { usePreferences } from '../../../shared/preferences';
import styles from './LandingPage.module.css';

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
    <section className={`page ${styles.landingRoot}`} aria-labelledby="landing-heading">
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

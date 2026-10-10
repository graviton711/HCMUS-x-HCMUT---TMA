import { useEffect, useRef, useState, type FormEvent, type MouseEventHandler } from 'react';
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

export function SupportPage({
  onStart,
  link,
}: {
  onStart: () => void;
  link: (url: string) => MouseEventHandler<HTMLAnchorElement>;
}) {
  const { t } = usePreferences();
  const guides = [
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
    [
      t('Xem một điều kiện thay đổi lựa chọn ra sao', 'See how one condition changes your options'),
      t(
        'Phân tích đánh đổi (what-if) đối chiếu các lựa chọn nếu bỏ một điều kiện, trong phạm vi dữ liệu của lượt tìm. Áp dụng một phương án mở bản nháp để bạn kiểm tra; chỉ tìm theo nhu cầu mới sau khi bạn xác nhận và yêu cầu tìm lại.',
        'Trade-off analysis (what-if) compares the options available if one condition is removed, within the data covered by that search. Applying a scenario opens a draft for review; searching with the new needs still requires your confirmation and a new search request.',
      ),
    ],
  ];
  const questions = [
    [
      t('Vì sao không có tour gợi ý?', 'Why are there no recommendations?'),
      t(
        'Có thể các tour đã đọc không đạt điều kiện bắt buộc, hoặc chưa đủ dữ kiện để xác nhận: thiếu địa điểm, lịch/giá đã cũ, phạm vi giá chưa rõ. Tour cần kiểm tra thêm trong bảng chưa phải gợi ý phù hợp. Xem lý do ở kết quả; chỉ điều chỉnh điều kiện khi bạn thực sự chấp nhận thay đổi. Kết quả bị giới hạn nguồn chưa đại diện toàn bộ thị trường.',
        'The tours read may fail a required condition or lack enough information to confirm it: missing locations, outdated dates or prices, or unclear price coverage. Tours marked for further checks are not recommendations. Review the reasons in the results and change a condition only if that change works for you. Results with limited source coverage do not represent the whole market.',
      ),
    ],
    [
      t(
        'Giá “Từ” và ngân sách có phải tổng tiền phải trả?',
        'Are a “From” price and the budget the final amount payable?',
      ),
      t(
        'Ô giá tour niêm yết/người lớn giới hạn giá tour đang được công bố cho mỗi người lớn. Nhãn “Từ” giữ ý nghĩa giá khởi điểm, không phải báo giá chắc chắn. Phụ thu bắt buộc, dịch vụ tùy chọn và khoản chưa rõ được xem riêng trong giá bao gồm/không bao gồm và chính sách. Giá dưới trần chưa chứng minh tổng thực trả dưới trần; kiểm tra đúng lịch, điều kiện áp dụng và hỏi nhà cung cấp trước khi đặt.',
        'The listed tour price per adult field limits the published tour price for each adult. “From” means a starting price, not a guaranteed quote. Mandatory surcharges, optional services and unclear costs are considered separately in inclusions, exclusions and policies. A listed price below the cap does not prove the total payable is below it; check the departure, applicable terms and supplier before booking.',
      ),
    ],
    [
      t(
        'Điều kiện bắt buộc và ưu tiên khác nhau thế nào?',
        'How do required conditions and preferences differ?',
      ),
      t(
        'Điều kiện bắt buộc như nơi đi, nơi đến, lịch và trần giá cần đạt theo nhu cầu đã xác nhận để tour vào nhóm gợi ý. Thiếu dữ kiện vẫn là chưa xác định. Ưu tiên giúp đánh giá tiếp các tour đã đạt, không bù cho điều kiện bắt buộc bị vi phạm. Một ưu tiên chưa được hỗ trợ hoặc thiếu nguồn sẽ được ghi rõ, không tự tạo điểm đánh giá.',
        'Required conditions such as origin, destination, dates and price cap must be met against your confirmed needs for a tour to enter the recommendation pool. Missing information remains unknown. Preferences help assess tours that qualify; they do not compensate for a failed required condition. Unsupported preferences or missing sources are disclosed rather than assigned invented scores.',
      ),
    ],
    [
      t(
        'Chọn nhiều tháng thì có lấy cả các tháng ở giữa không?',
        'Does selecting several months include the months in between?',
      ),
      t(
        'Mỗi tháng đi kèm năm và là một lựa chọn riêng. Chọn tháng 11/2026 và tháng 1/2027 chỉ tìm lịch khởi hành trong hai tháng đó, không thêm tháng 12. Tháng chỉ giới hạn ngày đi; nếu cần về trước một ngày, hãy nêu riêng trong nhu cầu và kiểm tra bản xác nhận.',
        'Each month includes a year and is a separate alternative. Selecting November 2026 and January 2027 searches departures in those two months without adding December. Months constrain departure dates only; if you need to return before a date, state that separately and review the confirmed requirements.',
      ),
    ],
    [
      t('What-if và các tỷ lệ nói lên điều gì?', 'What do what-if results and percentages mean?'),
      t(
        'What-if cho thấy lựa chọn có thể đổi thế nào khi bỏ một điều kiện, trên tập dữ liệu đã được đánh giá. Tỷ lệ phải đọc cùng số tour, phạm vi nguồn và phần chưa xác định; không phải phần trăm “độ quan trọng” của điều kiện hay xác suất chuyến đi thành công. Khi thiếu dữ liệu để tính, tỷ lệ có thể chưa có. Phân tích không tự thay đổi nhu cầu của bạn.',
        'What-if shows how the options may change when one condition is removed from the assessed data. Read percentages alongside tour counts, source coverage and unknowns; they are not the condition’s percentage “importance” or the probability of a successful trip. A percentage may be unavailable when data is insufficient. The analysis does not change your needs automatically.',
      ),
    ],
    [
      t(
        'Thấy giá, lịch hoặc thông tin tour sai thì báo thế nào?',
        'How can I report an incorrect price, departure or tour detail?',
      ),
      t(
        'Chọn “Báo thông tin tour sai”, kèm link tour, lịch khởi hành và nội dung cần kiểm tra. Có thể để lại email nếu muốn nhận phản hồi. Sau khi gửi, bạn nhận mã tiếp nhận để tham chiếu; đây là ghi nhận yêu cầu, chưa phải email đã gửi hoặc cam kết thời gian trả lời.',
        'Choose “Report incorrect tour information” and include the tour link, departure and the detail that needs checking. You can leave an email address if you would like a reply. Submission returns a reference number; it records your request and does not mean an email was sent or promise a response time.',
      ),
    ],
  ];
  const information = [
    [
      'sources',
      t('Nguồn dữ liệu và AI', 'Data sources and AI'),
      [
        t(
          'Thông tin tour đến từ các nguồn được hệ thống cấu hình và những URL được phép truy cập. Giá, lịch và chính sách giữ nguồn cùng thời điểm ghi nhận để bạn kiểm tra tại từng dữ kiện. Một lượt tìm có thể chỉ đọc được một phần kho tour; chưa có cam kết cập nhật nguồn định kỳ.',
          'Tour information comes from configured sources and URLs permitted for access. Prices, departures and policies retain their sources and observation times for you to check with each fact. A search may cover only part of the catalogue; there is no promised periodic source update schedule.',
        ),
        t(
          'AI hỗ trợ đọc nhu cầu và giải thích các tour sau bước kiểm tra điều kiện bắt buộc. Dữ kiện thiếu, lỗi đọc nguồn và ưu tiên chưa được đánh giá vẫn được giữ rõ. AI không xác nhận chỗ còn, tổng thực trả hoặc uy tín khi chưa có căn cứ. Lịch và giá cần thuộc cùng một lựa chọn khởi hành.',
          'AI helps interpret your needs and explain tours after required conditions are checked. Missing facts, source acquisition errors and unassessed preferences remain visible. AI does not confirm seat availability, the final payable amount or reputation without evidence. Dates and prices must belong to the same departure option.',
        ),
      ],
    ],
    [
      'privacy',
      t('Dữ liệu & quyền riêng tư', 'Data & privacy'),
      [
        t(
          'Trình duyệt lưu tên phiên, bản nháp và bản trao đổi đã nhận. Nhu cầu, tin nhắn và liên hệ đã gửi cũng được dịch vụ lưu và xử lý. Đăng nhập dùng Supabase Auth; nội dung liên quan tới nhu cầu và phân tích có thể được gửi tới dịch vụ AI để xử lý yêu cầu.',
          'The browser stores session names, drafts and received conversations. Submitted requirements, messages and contact requests are also stored and processed by the service. Sign-in uses Supabase Auth; content relevant to your needs and analysis may be sent to an AI service to process your request.',
        ),
        t(
          'Với tài khoản, lịch sử đã lưu có thể tải lại trên thiết bị khác trong thời hạn lưu của dịch vụ; bản nháp chưa gửi vẫn ở trình duyệt. “Ẩn lịch sử tài khoản” bỏ cuộc hội thoại khỏi danh sách, không xóa toàn bộ công việc và dữ kiện liên quan. Xóa bản lưu ẩn danh trên trình duyệt cũng không xóa bản ghi ở dịch vụ.',
          'Saved account history can be loaded on another device within the service’s retention period; unsent drafts remain in the browser. “Archive account history” removes conversations from the list without deleting all related jobs and evidence. Removing anonymous browser history also does not delete service records.',
        ),
      ],
    ],
    [
      'security',
      t('Quyền truy cập phiên', 'Session access'),
      [
        t(
          'Bạn có thể tìm tour bằng phiên ẩn danh. Quyền truy cập có thời hạn và được giữ trong phiên trình duyệt; các lượt cũ có thể không mở lại được khi quyền hết hạn. Thông tin cấp quyền không được đưa vào file xuất lịch sử.',
          'You can search using an anonymous session. Access expires and is held in browser session storage; older searches may become inaccessible after expiry. Access credentials are excluded from history exports.',
        ),
        t(
          'Đăng nhập để mở lịch sử đã lưu theo tài khoản. Nhập lịch sử ẩn danh vào tài khoản cần bạn chọn thao tác đó và phiên còn quyền truy cập. Đăng xuất chuyển về lịch sử ẩn danh riêng; không tự nhập lịch sử của một tài khoản khác.',
          'Sign in to open history saved to your account. Importing anonymous history requires an explicit action and a session with valid access. Signing out returns to separate anonymous history; another account’s history is not imported automatically.',
        ),
      ],
    ],
    [
      'scope',
      t('Phạm vi sử dụng', 'Scope of use'),
      [
        t(
          'Đi cùng hỗ trợ đối chiếu tour và nguồn thông tin; bạn tự quyết định và liên hệ nhà cung cấp để đặt. Sản phẩm chưa đặt tour, thanh toán hoặc xác nhận chỗ. Dữ kiện thiếu hoặc chưa xác minh được ghi rõ; cần kiểm tra lại giá, lịch và điều kiện với nhà cung cấp trước khi đặt.',
          'Đi cùng helps compare tours and sources; you decide and contact the supplier to book. The product does not book tours, process payments or confirm availability. Missing or unverified facts are marked; check prices, departures and terms with the supplier before booking.',
        ),
      ],
    ],
  ] as const;
  const reportUrl = '/contact?category=data_issue';
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
        <div className="support-content">
          <section className="support-section" aria-labelledby="compare">
            <h2 id="compare" tabIndex={-1}>
              {t('So sánh và xem đánh đổi', 'Compare and explore trade-offs')}
            </h2>
            <div className="support-articles">
              {guides.map(([title, text], index) => (
                <article key={title}>
                  <span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <section className="support-section" aria-labelledby="faq">
            <h2 id="faq" tabIndex={-1}>
              {t('Câu hỏi thường gặp', 'Frequently asked questions')}
            </h2>
            <div className="support-faq">
              {questions.map(([question, answer], index) => (
                <details key={index}>
                  <summary>
                    {question}
                    <Icon name="chevron" size={18} />
                  </summary>
                  <p>{answer}</p>
                </details>
              ))}
            </div>
            <a className="text-action support-report" href={reportUrl} onClick={link(reportUrl)}>
              {t('Báo thông tin tour sai', 'Report incorrect tour information')}
              <Icon name="arrow" size={16} />
            </a>
          </section>
          {information.map(([id, title, paragraphs]) => (
            <section className="support-section support-information" key={id} aria-labelledby={id}>
              <h2 id={id} tabIndex={-1}>
                {title}
              </h2>
              {paragraphs.map((text) => (
                <p key={text}>{text}</p>
              ))}
            </section>
          ))}
        </div>
        <aside className="service-note support-note">
          <nav
            className="support-contents"
            aria-label={t('Trong trang hỗ trợ', 'On this help page')}
          >
            <h2>{t('Bạn cần xem phần nào?', 'What would you like to read?')}</h2>
            {[
              ['compare', t('So sánh và đánh đổi', 'Comparison and trade-offs')],
              ['faq', t('Câu hỏi thường gặp', 'Frequently asked questions')],
              ...information.map(([id, title]) => [id, title]),
            ].map(([id, label]) => (
              <a key={id} href={`/support#${id}`} onClick={link(`/support#${id}`)}>
                {label}
              </a>
            ))}
          </nav>
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

type ContactCategory = 'feedback' | 'data_issue' | 'support';
function contactCategory(value?: string | null): ContactCategory {
  return value === 'data_issue' || value === 'support' ? value : 'feedback';
}

export function ContactPage({ requestedCategory }: { requestedCategory?: string | null }) {
  const { t } = usePreferences();
  const [category, setCategory] = useState<ContactCategory>(() =>
    contactCategory(requestedCategory),
  );
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ticket, setTicket] = useState('');
  const session = useRef<{ token: string; id: string } | null>(null);
  const sessionKey = useRef(crypto.randomUUID());
  const submission = useRef<{ fingerprint: string; id: string } | null>(null);
  useEffect(() => {
    setCategory(contactCategory(requestedCategory));
  }, [requestedCategory]);
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
                category === 'data_issue'
                  ? 'Link tour, lịch khởi hành và thông tin bạn thấy cần kiểm tra…'
                  : 'Điều bạn thấy hữu ích, hoặc muốn nhóm cải thiện…',
                category === 'data_issue'
                  ? 'Tour link, departure and the information you would like checked…'
                  : 'What you found useful, or what we could improve…',
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
          <p className="form-hint">
            {t(
              'Gửi form tạo mã tiếp nhận. Hệ thống chưa gửi email tự động hoặc cam kết thời gian phản hồi.',
              'Submitting creates a request reference. The service does not yet send automatic emails or promise a response time.',
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

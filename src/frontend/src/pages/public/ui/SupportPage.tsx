import { Icon } from '../../../shared/ui';
import { usePreferences } from '../../../shared/preferences';
import styles from './SupportPage.module.css';

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
    [
      t('Dữ liệu & quyền riêng tư', 'Data & privacy'),
      t(
        'Trình duyệt lưu tên phiên, bản nháp và nội dung trao đổi đã nhận. Nhu cầu, tin nhắn và nội dung liên hệ được gửi đến backend để xử lý; một số yêu cầu dùng dịch vụ AI. Xóa lịch sử trong Tài khoản chỉ xóa bản lưu trên trình duyệt, không xóa dữ liệu ở dịch vụ.',
        'This browser stores session names, drafts and received conversations. Requirements, messages and contact requests are sent to the backend; some requests use an AI service. Deleting history in Account removes this browser’s copy, not service records.',
      ),
      'privacy',
    ],
    [
      t('Quyền truy cập phiên', 'Session access'),
      t(
        'Phiên ẩn danh dùng token có thời hạn, lưu trong phiên trình duyệt và không kèm khi xuất lịch sử. Khi quyền hết hạn, các lượt cũ có thể không mở lại được. Lịch sử hiện chưa đồng bộ giữa các thiết bị.',
        'Anonymous sessions use expiring access tokens held in browser session storage and excluded from history exports. Old searches may be inaccessible after access expires. History is not yet synchronized across devices.',
      ),
      'security',
    ],
    [
      t('Phạm vi sử dụng', 'Scope of use'),
      t(
        'Đi cùng hỗ trợ đối chiếu tour và nguồn thông tin; bạn tự quyết định. Sản phẩm chưa đặt tour, thanh toán hoặc xác nhận chỗ. Dữ kiện thiếu hoặc chưa xác minh được ghi rõ; cần kiểm tra lại với nhà cung cấp trước khi đặt.',
        'Đi cùng helps compare tours and sources; you make the decision. The product does not book tours, process payments or confirm availability. Missing or unverified facts are marked; check with the supplier before booking.',
      ),
      'scope',
    ],
  ];
  return (
    <section className={`page ${styles.supportRoot}`} aria-labelledby="support-heading">
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
          {articles.map(([title, text, id], index) => (
            <article key={index} id={id}>
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

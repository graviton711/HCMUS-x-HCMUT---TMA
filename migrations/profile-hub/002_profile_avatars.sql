-- Run in the Supabase Auth project, after reviewing the account photo contract.
begin;
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('profile-avatars', 'profile-avatars', false, 65536, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = 65536,
  allowed_mime_types = array['image/jpeg'];

drop policy if exists profile_avatar_read on storage.objects;
create policy profile_avatar_read on storage.objects for select to authenticated
using (bucket_id = 'profile-avatars' and name = (select auth.uid())::text || '/avatar.jpg');

drop policy if exists profile_avatar_insert on storage.objects;
create policy profile_avatar_insert on storage.objects for insert to authenticated
with check (bucket_id = 'profile-avatars' and name = (select auth.uid())::text || '/avatar.jpg');

drop policy if exists profile_avatar_update on storage.objects;
create policy profile_avatar_update on storage.objects for update to authenticated
using (bucket_id = 'profile-avatars' and name = (select auth.uid())::text || '/avatar.jpg')
with check (bucket_id = 'profile-avatars' and name = (select auth.uid())::text || '/avatar.jpg');

drop policy if exists profile_avatar_delete on storage.objects;
create policy profile_avatar_delete on storage.objects for delete to authenticated
using (bucket_id = 'profile-avatars' and name = (select auth.uid())::text || '/avatar.jpg');
commit;

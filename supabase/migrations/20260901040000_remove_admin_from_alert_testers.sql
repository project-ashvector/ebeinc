-- Remove the station administrator from the temporary alert-repair tester cohort.
-- This does not alter the existing admin role or any unrelated account data.

delete from public.account_classes c
using auth.users u
where c.user_id = u.id
  and c.source = 'manual_test'
  and lower(u.email) = 'allthings140@gmail.com';

delete from public.alert_test_accounts
where email = 'allthings140@gmail.com';

/* Custom startup skips GCC constructors. Register counters at raw exit so
 * GCC writes complete run summaries as well as branch/value counters. */
#ifdef DEWY_PROFILE_GENERATE
#include <gcov.h>
extern struct gcov_info *__start_gcov_info[], *__stop_gcov_info[];
extern void __gcov_init(struct gcov_info *);
void *__dso_handle = &__dso_handle;
#endif
__attribute__((no_profile_instrument_function))
void dewy_host_profile_dump(void) {
#ifdef DEWY_PROFILE_GENERATE
  for (struct gcov_info **p = __start_gcov_info; p != __stop_gcov_info; ++p)
    __gcov_init(*p);
  __gcov_dump();
#endif
}

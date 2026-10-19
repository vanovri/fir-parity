program fir
  use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
  implicit none
  character(len=4096) :: taps_file, signal_file, out_file
  integer :: m, n, i, k, ios, unit_out
  real(8), allocatable :: c(:), x(:), y(:)
  real(8) :: acc
  if (command_argument_count() /= 3) stop 2
  call get_command_argument(1, taps_file)
  call get_command_argument(2, signal_file)
  call get_command_argument(3, out_file)
  call read_series(trim(taps_file), c, m)
  call read_series(trim(signal_file), x, n)
  if (m < 1) stop 4
  if (int(m,8)*int(n,8) > 20000000_8) stop 4
  allocate(y(n))
  do i = 1, n
    acc = 0.0d0
    do k = 1, m
      if (i-k+1 >= 1) acc = acc + c(k)*x(i-k+1)
    end do
    if (.not. ieee_is_finite(acc)) stop 8
    y(i) = acc
  end do
  ! Never overwrite an input or an existing result.
  open(newunit=unit_out, file=trim(out_file), status='new', action='write', iostat=ios)
  if (ios /= 0) stop 9
  write(unit_out, '(I0)') n
  do i = 1, n
    write(unit_out, '(ES24.16E3)') y(i)
  end do
  close(unit_out)
contains
  subroutine read_series(filename, values, count)
    character(len=*), intent(in) :: filename
    real(8), allocatable, intent(out) :: values(:)
    integer, intent(out) :: count
    integer :: unit_in, status, j
    character(len=512) :: line
    open(newunit=unit_in, file=filename, status='old', action='read', iostat=status)
    if (status /= 0) stop 3
    read(unit_in, '(A)', iostat=status) line
    if (status /= 0) stop 4
    line = adjustl(line)
    if (len_trim(line) < 1 .or. len_trim(line) > 7) stop 4
    if (verify(trim(line), '0123456789') /= 0) stop 4
    read(line, *, iostat=status) count
    if (status /= 0 .or. count > 1000000) stop 4
    allocate(values(count))
    do j = 1, count
      read(unit_in, '(A)', iostat=status) line
      if (status /= 0) stop 5
      line = adjustl(line)
      if (len_trim(line) < 1) stop 5
      if (verify(trim(line), '0123456789Ee+-.') /= 0) stop 5
      read(line, *, iostat=status) values(j)
      if (status /= 0) stop 5
      if (.not. ieee_is_finite(values(j))) stop 5
    end do
    read(unit_in, '(A)', iostat=status) line
    if (status >= 0) stop 5
    close(unit_in)
  end subroutine read_series
end program fir

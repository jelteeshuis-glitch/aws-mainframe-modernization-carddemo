package com.aws.carddemo.cardlist.service;

/**
 * Requested paging action, mirroring the PF-keys handled by {@code COCRDLIC}:
 * <ul>
 *   <li>{@link #FIRST} - fresh entry / ENTER: list from the top.</li>
 *   <li>{@link #NEXT} - PF8 page down.</li>
 *   <li>{@link #PREV} - PF7 page up.</li>
 * </ul>
 */
public enum PageDirection {
    FIRST,
    NEXT,
    PREV
}
